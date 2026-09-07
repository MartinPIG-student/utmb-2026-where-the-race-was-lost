"""
utmb_course
===========

Exploitation des traces GPX (sans horodatage) des 4 coureurs pour reconstruire
la **géométrie réelle du parcours** : profil d'altitude haute résolution, pente
locale réelle moyennée sur les 4 traces, et pente moyenne réelle de chaque
kilomètre entier.

Les GPX ne contiennent que lat / lon / altitude → aucune information de temps ou
d'allure n'en est tirée. On s'en sert uniquement pour remplacer la pente estimée
à partir du dénivelé *net* par km (grossière) par la vraie pente du terrain.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

_NS = {"g": "http://www.topografix.com/GPX/1/1"}

GPX_FILES = {
    "dhiman": "dhiman.gpx",
    "olson": "olson.gpx",
    "moriset": "moriset.gpx",
    "lopez": "lopez.gpx",
}

STEP_M = 20.0            # pas de rééchantillonnage le long du parcours
SMOOTH_WINDOW_M = 200.0  # fenêtre de lissage de l'altitude (Savitzky-Golay)
FLAT_PCT = 3.0           # seuil |pente| en dessous duquel un km est classé "plat"


# --------------------------------------------------------------------------- #
# Lecture GPX
# --------------------------------------------------------------------------- #

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def load_track(path: str | Path) -> pd.DataFrame:
    """GPX -> DataFrame (lat, lon, ele, dist_m cumulée le long de la trace)."""
    root = ET.parse(path).getroot()
    pts = root.findall(".//g:trkpt", _NS)
    lat = np.array([float(p.get("lat")) for p in pts])
    lon = np.array([float(p.get("lon")) for p in pts])
    ele = np.array([float(p.find("g:ele", _NS).text) for p in pts])

    seg = _haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dist = np.concatenate([[0.0], np.cumsum(seg)])

    # Points quasi immobiles (bruit GPS à l'arrêt) : on ne les supprime pas,
    # le rééchantillonnage par distance les absorbe.
    return pd.DataFrame({"lat": lat, "lon": lon, "ele": ele, "dist_m": dist})


def _resample(track: pd.DataFrame, step_m: float = STEP_M) -> pd.DataFrame:
    """Rééchantillonne la trace à pas de distance constant + lisse l'altitude."""
    grid = np.arange(0.0, track["dist_m"].iloc[-1], step_m)
    ele = np.interp(grid, track["dist_m"], track["ele"])
    lat = np.interp(grid, track["dist_m"], track["lat"])
    lon = np.interp(grid, track["dist_m"], track["lon"])

    win = int(round(SMOOTH_WINDOW_M / step_m))
    win = max(5, win | 1)  # impair
    if len(ele) > win:
        ele_s = savgol_filter(ele, win, polyorder=2)
    else:
        ele_s = ele
    # Pente locale, bornée à ±45 % (au-delà = artefact GPS ; les sentiers
    # de l'UTMB dépassent rarement 35 % de pente moyenne sur 20 m).
    grade = np.clip(np.gradient(ele_s, step_m) * 100.0, -45.0, 45.0)
    return pd.DataFrame({"dist_m": grid, "ele": ele_s, "ele_raw": ele,
                         "grade_pct": grade, "lat": lat, "lon": lon})


# --------------------------------------------------------------------------- #
# Profil commun + caractérisation par kilomètre
# --------------------------------------------------------------------------- #

def load_all_tracks(gpx_dir: str | Path) -> dict[str, pd.DataFrame]:
    return {k: _resample(load_track(Path(gpx_dir) / fn))
            for k, fn in GPX_FILES.items()}


def reference_profile(tracks: dict[str, pd.DataFrame],
                      step_m: float = STEP_M) -> pd.DataFrame:
    """Profil unique : altitude et pente moyennées sur les 4 traces, sur la
    longueur commune (rééchantillonnage sur une distance normalisée)."""
    lengths = {k: t["dist_m"].iloc[-1] for k, t in tracks.items()}
    L = min(lengths.values())
    grid = np.arange(0.0, L, step_m)

    ele_stack, grade_stack, lat_stack, lon_stack = [], [], [], []
    for t in tracks.values():
        ele_stack.append(np.interp(grid, t["dist_m"], t["ele"]))
        grade_stack.append(np.interp(grid, t["dist_m"], t["grade_pct"]))
        lat_stack.append(np.interp(grid, t["dist_m"], t["lat"]))
        lon_stack.append(np.interp(grid, t["dist_m"], t["lon"]))
    ele = np.mean(ele_stack, axis=0)
    grade = np.mean(grade_stack, axis=0)

    return pd.DataFrame({
        "dist_km": grid / 1000.0,
        "altitude_m": ele,
        "grade_pct": grade,
        "lat": np.mean(lat_stack, axis=0),
        "lon": np.mean(lon_stack, axis=0),
        "altitude_spread_m": np.max(ele_stack, axis=0) - np.min(ele_stack, axis=0),
    })


def map_checkpoints(reference: pd.DataFrame, checkpoints: pd.DataFrame) -> pd.DataFrame:
    """Place chaque point de contrôle (km officiel) sur l'axe kilométrique de
    l'analyse, par plus proche voisin lat/lon sur le profil de référence."""
    if checkpoints is None:
        return None
    lat0 = np.radians(reference["lat"].to_numpy())
    lon0 = np.radians(reference["lon"].to_numpy())
    km_axis = reference["dist_km"].to_numpy()
    out = checkpoints.copy()
    mapped = []
    for _, c in checkpoints.iterrows():
        dlat = lat0 - np.radians(c["lat"])
        dlon = lon0 - np.radians(c["lon"])
        d2 = dlat ** 2 + (dlon * np.cos(lat0)) ** 2
        mapped.append(round(float(km_axis[int(np.argmin(d2))]), 2))
    out["km_axis"] = mapped
    return out


def per_km_profile(tracks: dict[str, pd.DataFrame],
                   n_km: int | None = None) -> pd.DataFrame:
    """Pente moyenne réelle (`grade_mean`, %) de chaque kilomètre entier,
    moyennée sur les 4 traces."""
    per_runner = []
    for t in tracks.values():
        km_idx = np.floor(t["dist_m"] / 1000.0).astype(int) + 1
        df = pd.DataFrame({"km": km_idx, "grade": t["grade_pct"].to_numpy()})
        per_runner.append(df.groupby("km").agg(grade_mean=("grade", "mean")))

    out = (sum(x.fillna(0) for x in per_runner) / len(per_runner)).reset_index()
    if n_km is not None:
        out = out[out["km"].between(1, n_km)].reset_index(drop=True)
    return out


# --------------------------------------------------------------------------- #
# Points de contrôle (roadbook)
# --------------------------------------------------------------------------- #

def load_checkpoints(path: str | Path) -> pd.DataFrame | None:
    """Charge le CSV des points de contrôle si présent (nom, km, altitude_m,
    lat, lon, type). Généré par `extract_checkpoints` depuis le GPX officiel."""
    path = Path(path)
    if not path.exists():
        return None
    cp = pd.read_csv(path)
    cp.columns = [c.strip().lower() for c in cp.columns]
    return cp


_COL_WORDS = ("col ", "voza", "bonhomme", "seigne", "favre", "ferret",
              "tseppes", "giète", "giete", "checrouit", "checroui")


def extract_checkpoints(official_gpx: str | Path) -> pd.DataFrame:
    """Extrait les waypoints (points de contrôle) du GPX officiel du parcours :
    nom, km (depuis `<extensions><distance>`), altitude, lat/lon, type."""
    root = ET.parse(official_gpx).getroot()
    rows = []
    for w in root.findall(".//g:wpt", _NS):
        nm = (w.find("g:name", _NS).text or "").strip()
        if nm in ("", "UTMB®"):
            continue
        ele = float(w.find("g:ele", _NS).text)
        dist_el = w.find("g:extensions/g:distance", _NS)
        km = round(float(dist_el.text) / 1000, 1) if dist_el is not None else np.nan
        lat, lon = float(w.get("lat")), float(w.get("lon"))
        low = nm.lower()
        if km == 0:
            typ = "depart"
        elif "chamonix" in low and km and km > 100:
            typ = "arrivee"
        elif any(c in low for c in _COL_WORDS) and "sortie" not in low:
            typ = "col"
        else:
            typ = "ravito"
        rows.append({"nom": nm, "km": km, "altitude_m": round(ele),
                     "lat": round(lat, 5), "lon": round(lon, 5), "type": typ})
    return pd.DataFrame(rows)
