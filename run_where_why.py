"""
UTMB 2026 — reconstruction des données OÙ / POURQUOI.

Combine les splits Strava km par km (temps, allure, VAP, cadence) avec la
géométrie réelle du parcours reconstruite depuis les traces GPX (pente locale
réelle, tronçons, technicité).

Ce module n'expose que build(), qui renvoie toutes les données organisées
nécessaires à `make_post_figures.py` pour produire `tableau_data.xlsx`
(le classeur qui alimente les 4 figures publiées sur Tableau Public).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import utmb_pacing as up      # noqa: E402
import utmb_course as uc      # noqa: E402

DATA_DIR = ROOT / "utmb_2026_data"
GPX_DIR = DATA_DIR / "gpx"

ORDER = ["dhiman", "olson", "moriset", "lopez"]
REF = "dhiman"
CHASERS = ["olson", "moriset", "lopez"]


# --------------------------------------------------------------------------- #

def build():
    runners = {k: up.load_all(DATA_DIR)[k] for k in ORDER}
    names = {k: runners[k].name for k in ORDER}

    tracks = uc.load_all_tracks(GPX_DIR)
    reference = uc.reference_profile(tracks)
    n_km = int(min(t["dist_m"].iloc[-1] for t in tracks.values()) // 1000)  # ~167
    kmprof = uc.per_km_profile(tracks, n_km=n_km)
    # Points de contrôle : (re)générés depuis le GPX officiel du parcours.
    cp_csv = DATA_DIR / "course_checkpoints.csv"
    official = GPX_DIR / "_official_course.gpx"
    if official.exists():
        uc.extract_checkpoints(official).to_csv(cp_csv, index=False, encoding="utf-8")
    checkpoints = uc.map_checkpoints(reference, uc.load_checkpoints(cp_csv))

    # ---- temps segment recalé + gap cumulé au vainqueur ------------------- #
    n_common, cf = up.common_frame(runners)
    n = min(n_common, n_km, len(kmprof))
    grade = kmprof.set_index("km")["grade_mean"].reindex(range(1, n + 1)).to_numpy()
    terrain = np.where(grade > uc.FLAT_PCT, "montée",
               np.where(grade < -uc.FLAT_PCT, "descente", "plat"))

    seg = {}
    for k in ORDER:
        d = cf[k].iloc[:n].copy()
        d["grade_real"] = grade
        d["terrain"] = terrain
        d["cum_gap_s"] = (d["seg_time_scaled_s"].cumsum()
                          - cf[REF]["seg_time_scaled_s"].iloc[:n].cumsum())
        seg[k] = d

    vr = pd.DataFrame({"km": seg[REF]["cum_dist_km"].to_numpy()})
    for k in ORDER:
        vr[k] = seg[k]["cum_gap_s"].to_numpy()

    # ---- écart de VAP au vainqueur, km par km -------------------------- #
    # On écarte deux types de km, dont l'allure ne reflète pas la course :
    #  (a) fenêtre autour des ravitaillements (axe km du profil de référence) ;
    #  (b) pics d'écart de VAP > 80 s/km vs le vainqueur — aucun coureur n'est
    #      réellement 80 s/km plus lent que Dhiman à pente égale sur 1 km entier :
    #      c'est un arrêt (drop bag), une chute ou une erreur de nav. Ce filtre
    #      rattrape les gros arrêts (Courmayeur) que la fenêtre (a) manque à
    #      cause du décalage entre l'axe de référence et le kilométrage Strava
    #      de chaque coureur.
    SPIKE_S_KM = 80.0
    aid_km = set()
    if checkpoints is not None:
        for _, c in checkpoints.iterrows():
            if c["type"] in ("ravito", "arrivee"):
                base = int(np.floor(c["km_axis"]))
                aid_km.update({base, base + 1, base + 2})
    not_aid = np.array([(i + 1) not in aid_km for i in range(n)])
    cum = seg[REF]["cum_dist_km"].to_numpy()
    third = np.where(cum <= n / 3, "1er tiers",
             np.where(cum <= 2 * n / 3, "2e tiers", "3e tiers"))
    dv = seg[REF]["vap_s"].to_numpy()
    dist = seg[REF]["dist_km"].to_numpy()

    # Masque « exploitable » propre à chaque coureur.
    vgap = {k: seg[k]["vap_s"].to_numpy() - dv for k in CHASERS}
    usable = {k: not_aid & (np.abs(vgap[k]) <= SPIKE_S_KM) for k in CHASERS}

    # Contribution de chaque km au retard, ajustée à la pente :
    #   gap_km = (VAP_coureur - VAP_Dhiman) * distance_km
    graded = {k: vgap[k] * dist for k in CHASERS}

    # ---- écart de VAP par terrain et par tiers de course -------------- #
    vap_rows = []
    for k in CHASERS:
        gapv, u = vgap[k], usable[k]
        for t in ("montée", "descente"):
            for th in ("1er tiers", "2e tiers", "3e tiers"):
                m = (terrain == t) & (third == th) & u
                vap_rows.append({"coureur": names[k], "coureur_key": k,
                                 "terrain": t, "tiers": th,
                                 "ecart_vap_s_km": float(gapv[m].mean())})
            m = (terrain == t) & u
            vap_rows.append({"coureur": names[k], "coureur_key": k,
                             "terrain": t, "tiers": "toute la course",
                             "ecart_vap_s_km": float(gapv[m].mean())})
    vap_terr = pd.DataFrame(vap_rows)

    # ---- mécanique de descente : cadence / foulée vs Dhiman ------------- #
    d_cad = seg[REF]["cadence_ppm"].to_numpy()
    d_str = seg[REF]["stride_m"].to_numpy()
    steep_dn = terrain == "descente"
    mech = []
    for k in CHASERS + [REF]:
        s = seg[k]
        vg = s["vap_s"].to_numpy() - dv
        cgap = s["cadence_ppm"].to_numpy() - d_cad
        sgap = (s["stride_m"].to_numpy() - d_str) * 100
        u = usable[k] if k != REF else not_aid
        m = steep_dn & u
        mech.append({
            "coureur": names[k], "coureur_key": k,
            "vap_gap_desc": float(vg[m].mean()) if k != REF else 0.0,
            "cad_gap_desc": float(cgap[m].mean()) if k != REF else 0.0,
            "stride_gap_desc_cm": float(sgap[m].mean()) if k != REF else 0.0,
        })
    mech = pd.DataFrame(mech)

    return dict(names=names, reference=reference, checkpoints=checkpoints, vr=vr,
                mech=mech, vap_terr=vap_terr, terrain=terrain, graded=graded,
                usable=usable, km_axis=cum)
