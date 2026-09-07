"""
utmb_pacing
===========

Chargement et nettoyage des splits Strava km par km de l'UTMB 2026
(4 coureurs de tête). Fournit `load_all()` et `common_frame()`, seules
fonctions consommées par `run_where_why.build()`.

Dépendances : pandas, numpy uniquement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Métadonnées coureurs (classement et temps officiels UTMB 2026)
# --------------------------------------------------------------------------- #

RUNNERS = {
    "dhiman":  {"file": "dhiman_utmb2026.xlsx",  "name": "Ben Dhiman"},
    "olson":   {"file": "olson_utmb2026.xlsx",   "name": "Caleb Olson"},
    "moriset": {"file": "moriset_utmb2026.xlsx", "name": "Virgile Moriset"},
    "lopez":   {"file": "lopez_utmb2026.xlsx",   "name": "Joaquin Lopez"},
}


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #

_PACE_RE = re.compile(r"^\s*(\d+):(\d{2})\s*/?\s*km\s*$")


def parse_pace_to_seconds(value) -> float:
    """'4:03/km' -> 243.0 (secondes par kilomètre). NaN si non parsable."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    m = _PACE_RE.match(str(value).replace("\xa0", " "))
    if not m:
        return np.nan
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_cadence(value) -> float:
    """'172 ppm' -> 172.0"""
    if value is None:
        return np.nan
    s = re.sub(r"[^\d.]", "", str(value).replace("\xa0", " "))
    return float(s) if s else np.nan


def parse_km_label(value) -> float:
    """
    Étiquette de la colonne KM.

    Entier -> distance du segment = 1.0 km.
    Nombre décimal type '0,57' -> dernier segment partiel de 0.57 km.
    """
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    return float(s)


def elapsed_to_seconds(value) -> float:
    """datetime.time(18, 16, 29) ou '18:16:29' -> 65789.0 secondes."""
    if isinstance(value, time):
        return value.hour * 3600 + value.minute * 60 + value.second
    parts = [int(p) for p in str(value).split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


# --------------------------------------------------------------------------- #
# Chargement
# --------------------------------------------------------------------------- #

@dataclass
class RunnerData:
    key: str
    name: str
    elapsed_seconds: float
    df: pd.DataFrame = field(repr=False)

    @property
    def pace_sum_seconds(self) -> float:
        """Temps de course reconstruit = somme (allure * distance segment)."""
        return float((self.df["allure_s"] * self.df["dist_km"]).sum())


def _is_number_like(v) -> bool:
    try:
        float(str(v).replace(",", "."))
        return True
    except ValueError:
        return False


def _is_integerish(v) -> bool:
    if not _is_number_like(v):
        return False
    return float(str(v).replace(",", ".")).is_integer()


def _read_one(path: Path) -> tuple[str, float, pd.DataFrame]:
    raw = pd.read_excel(path, header=None, engine="openpyxl")

    # Nom + Elapsed Time : sur la ligne qui suit l'en-tête "Name".
    name_hdr_row = raw.index[raw[0].astype(str).str.strip().str.lower() == "name"][0]
    name = str(raw.iloc[name_hdr_row + 1, 0]).strip()
    elapsed_seconds = elapsed_to_seconds(raw.iloc[name_hdr_row + 1, 1])

    # Tableau km : commence à la ligne d'en-tête "KM".
    km_hdr_row = raw.index[raw[0].astype(str).str.strip() == "KM"][0]
    table = raw.iloc[km_hdr_row + 1:, :5].copy()
    table.columns = ["KM", "Allure", "VAP", "Alt.", "Cadence"]
    table = table[table["KM"].notna()].reset_index(drop=True)

    out = pd.DataFrame()
    # dist_km : 1.0 pour un km plein, valeur fractionnaire pour le segment
    # final partiel (étiquette type "0,57").
    out["dist_km"] = [
        (1.0 if _is_integerish(lbl) else parse_km_label(lbl))
        for lbl in table["KM"]
    ]
    out["allure_s"] = table["Allure"].map(parse_pace_to_seconds)
    out["vap_s"] = table["VAP"].map(parse_pace_to_seconds)
    out["cadence_ppm"] = table["Cadence"].map(parse_cadence)

    out["cum_dist_km"] = out["dist_km"].cumsum()

    # Mécanique de foulée.
    # speed_ms : vitesse au sol sur le segment.
    # stride_m : longueur de foulée estimée = vitesse / fréquence de pas.
    #   NB : proxy relatif — l'unité exacte dépend de la convention Strava pour
    #   la cadence (un pied vs deux). Les comparaisons et tendances restent valides.
    out["speed_ms"] = 1000.0 / out["allure_s"]
    out["stride_m"] = out["speed_ms"] / (out["cadence_ppm"] / 60.0)

    # Temps passé sur le segment (s) = allure * distance.
    out["seg_time_s"] = out["allure_s"] * out["dist_km"]

    return name, elapsed_seconds, out


def load_runner(key: str, data_dir: str | Path) -> RunnerData:
    meta = RUNNERS[key]
    path = Path(data_dir) / meta["file"]
    name, elapsed_seconds, df = _read_one(path)
    return RunnerData(
        key=key,
        name=name or meta["name"],
        elapsed_seconds=elapsed_seconds,
        df=df,
    )


def load_all(data_dir: str | Path) -> dict[str, RunnerData]:
    return {k: load_runner(k, data_dir) for k in RUNNERS}


# --------------------------------------------------------------------------- #
# Cadre commun : temps de segment recalé sur le temps officiel
# --------------------------------------------------------------------------- #

def common_frame(runners: dict[str, RunnerData]) -> tuple[int, dict[str, pd.DataFrame]]:
    """Les 4 coureurs restreints à la plage de km commune, temps recalé sur
    le temps officiel (le temps de chaque segment est mis à l'échelle par
    `Elapsed / somme des allures`, ce qui répartit les arrêts proportionnellement
    et rend les 4 coureurs comparables sur une base « temps écoulé »)."""
    n = min(len(r.df) for r in runners.values())
    out: dict[str, pd.DataFrame] = {}
    for k, r in runners.items():
        d = r.df.iloc[:n].reset_index(drop=True).copy()
        scale = r.elapsed_seconds / r.pace_sum_seconds
        d["seg_time_scaled_s"] = d["seg_time_s"] * scale
        out[k] = d
    return n, out
