"""
Données « publication » pour les figures Tableau Public du post LinkedIn/Notion.

Les 4 figures elles-mêmes sont construites dans Tableau Public, pas ici — ce
script ne produit que le classeur de données qui les alimente.

Usage :  python make_post_figures.py
Sortie :  post_figures/tableau_data.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import run_where_why as W  # noqa: E402

OUT = ROOT / "post_figures"
OUT.mkdir(exist_ok=True)

CHASERS = ["olson", "moriset", "lopez"]

# Noms courts et lisibles pour les points de contrôle (aide à la lecture)
CP_SHORT = {
    "Chamonix": "Chamonix",
    "Saint-Gervais": "Saint-Gervais",
    "Les Contamines Montjoie": "Les Contamines",
    "La Balme": "La Balme",
    "Les Chapieux": "Les Chapieux",
    "Lac Combal": "Lac Combal",
    "Courmayeur Sport Center Sortie": "Courmayeur",
    "Refuge Bertone": "Bertone",
    "Refuge Bonatti": "Bonatti",
    "Arnouvaz": "Arnuva",
    "La Fouly": "La Fouly",
    "Champex-Lac sortie": "Champex-Lac",
    "Plan de l'Au": "Plan de l'Au",
    "Trient": "Trient",
    "Vallorcine Sortie": "Vallorcine",
    "La Flégère": "La Flégère",
}


def export_tableau_data(ctx):
    """Données en format long, noms anglais — prêtes pour Tableau Public.
    Un onglet par figure + une table par « couche » de la figure 1."""
    names, vr = ctx["names"], ctx["vr"]
    finish = {"olson": "3rd", "moriset": "4th", "lopez": "5th"}
    km = vr["km"].to_numpy()

    # --- Figure 1 : 3 tables ---
    # time lost (long)
    tl = []
    for k in CHASERS:
        raw = vr[k].to_numpy() / 60
        sm = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().to_numpy()
        for x, r, s in zip(km, raw, sm):
            tl.append({"km": round(x, 2), "runner": f"{names[k]} ({finish[k]})",
                       "time_lost_min_raw": round(r, 2),
                       "time_lost_min_smooth": round(s, 2)})
    f1_time = pd.DataFrame(tl)

    ref = ctx["reference"]
    cps = ctx["checkpoints"]
    aid = cps[cps["type"].isin(["ravito", "arrivee"])].copy()
    aid["elev"] = np.interp(aid["km_axis"], ref["dist_km"], ref["altitude_m"])

    # Une seule table pour le panneau du haut : lignes du profil (aid_name vide)
    # + lignes des ravitos (aid_name renseigné, altitude interpolée).
    prof = pd.DataFrame({"km": ref["dist_km"].round(2),
                         "elevation_m": ref["altitude_m"].round(0),
                         "aid_name": ""})
    aidrows = pd.DataFrame({"km": aid["km_axis"].round(2),
                            "elevation_m": aid["elev"].round(0),
                            "aid_name": aid["nom"].map(lambda n: CP_SHORT.get(n, n))})
    f1_elev = pd.concat([prof, aidrows], ignore_index=True).sort_values("km")

    # Table des ravitos seule (km + nom) — pour les lignes verticales du bas.
    f1_aid = aidrows.rename(columns={"aid_name": "name"})[["km", "name"]]

    # --- Figure 2 : contribution par terrain (long) ---
    terrain, kma = ctx["terrain"], ctx["km_axis"]
    graded = ctx["graded"]
    f2 = []
    for k in CHASERS:
        diff = graded[k] * ctx["usable"][k]
        cum = {t: np.cumsum(np.where(terrain == t, diff, 0.0)) / 60
               for t in ("descente", "montée", "plat")}
        for i, x in enumerate(kma):
            for t, en in (("descente", "downhill"), ("montée", "uphill"),
                          ("plat", "flat")):
                f2.append({"km": round(x, 2), "runner": f"{names[k]} ({finish[k]})",
                           "terrain": en, "cum_time_lost_min": round(cum[t][i], 3)})
    f2 = pd.DataFrame(f2)

    # --- Figure 3 : heatmap déficit VAP (long) ---
    vt = ctx["vap_terr"]
    terr_en = {"descente": "downhill", "montée": "uphill"}
    tiers_en = {"1er tiers": "1st third", "2e tiers": "2nd third",
                "3e tiers": "3rd third", "toute la course": "whole race"}
    f3 = (vt[vt.coureur_key.isin(CHASERS)]
          .assign(runner=lambda d: d["coureur"],
                  terrain=lambda d: d["terrain"].map(terr_en),
                  race_third=lambda d: d["tiers"].map(tiers_en),
                  pace_deficit_s_per_km=lambda d: d["ecart_vap_s_km"].round(1))
          [["runner", "terrain", "race_third", "pace_deficit_s_per_km"]])

    # --- Figure 4 : mécanique de descente (cadence / foulée vs vainqueur) ---
    mech = ctx["mech"].set_index("coureur_key")
    f4 = [{"runner": "Ben Dhiman (1st)", "cadence_gap_ppm": 0.0,
           "stride_gap_cm": 0.0, "descent_gap_s_per_km": 0.0, "is_winner": 1}]
    for k in CHASERS:
        f4.append({"runner": f"{names[k]} ({finish[k]})",
                   "cadence_gap_ppm": round(float(mech.loc[k, "cad_gap_desc"])),
                   "stride_gap_cm": round(float(mech.loc[k, "stride_gap_desc_cm"])),
                   "descent_gap_s_per_km": round(float(mech.loc[k, "vap_gap_desc"])),
                   "is_winner": 0})
    f4 = pd.DataFrame(f4)

    path = OUT / "tableau_data.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        f1_time.to_excel(xl, sheet_name="fig1_time_lost", index=False)
        f1_elev.to_excel(xl, sheet_name="fig1_elevation", index=False)
        f1_aid.to_excel(xl, sheet_name="fig1_aid_stations", index=False)
        f2.to_excel(xl, sheet_name="fig2_by_terrain", index=False)
        f3.to_excel(xl, sheet_name="fig3_speed_deficit", index=False)
        f4.to_excel(xl, sheet_name="fig4_descent_mechanics", index=False)
    print(f"  {path.relative_to(ROOT)}")


def main():
    ctx = W.build()
    export_tableau_data(ctx)


if __name__ == "__main__":
    main()
