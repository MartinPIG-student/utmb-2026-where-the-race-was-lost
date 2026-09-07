# UTMB 2026 — Where the time gap opens between the leaders, and how

Kilometre-by-kilometre reconstruction of the race for four of the men's top 5 at
the 2026 UTMB (Chassagne excluded), from their **Strava splits** and **GPX
tracks**: where the time gap to the winner opens, and by what mechanism.

> Portfolio project: data processing applied to trail-running performance. Code,
> method and limitations are documented to be read back.

**The four interactive charts are published on Tableau Public:**
https://public.tableau.com/app/profile/martin.pigeau/viz/UTMB2026-Wheretheracewaslost/Figures

**Full write-up (Notion):** _link to come_

This repository holds only the data pipeline that produces the Excel workbook
those charts read from — not the charts themselves, which are built and
maintained directly in Tableau Public.

---

## Key result

**Ben Dhiman (1st) made the difference on the descents.** There is no single
attack: the gap opens almost continuously over the whole race. Once slope is
neutralised and stops are removed, **60.6% to 70.7%** of each chaser's
grade-adjusted deficit is paid going downhill; on the climbs the three are close
to parity with Dhiman (+5 to +16 s/km), against +12 to +30 s/km downhill.

Each one loses differently:

- **Caleb Olson** — deficit that shrinks gradually, near zero (uphill and
  downhill) over the final third of the race.
- **Virgile Moriset** — uphill deficit that disappears, but downhill deficit
  that stays high from start to finish.
- **Joaquin Lopez** — deficit that worsens third by third, uphill and downhill:
  a progressive decline, not a one-off.

The mechanism, on downhill kilometres only (step rate and step length vs Dhiman):

- **Olson and Lopez** take more steps per minute than Dhiman (+14 and +16 ppm)
  and a shorter step (−15 cm, −21 cm): a braking signature.
- **Moriset** keeps Dhiman's cadence (+1 ppm) but covers less ground per step
  (−13 cm): he doesn't brake more, he simply advances less at each footstrike.

## 1. Question

The study locates **where the time gap opens** between the four runners along
the ~167 km they have in common, then **identifies the mechanism** behind that
loss of ground at those specific spots.

## 2. Data

Two sources, both **public**:

**Kilometre-by-kilometre Strava splits** — one Excel file per runner in
[`utmb_2026_data/`](utmb_2026_data/) (one row per km: pace, grade-adjusted pace,
elevation change, cadence).

| Runner | Place | Official time | File |
|---|---|---|---|
| Ben Dhiman | 1st | 18:16:29 | `dhiman_utmb2026.xlsx` |
| Caleb Olson | 3rd | 18:48:24 | `olson_utmb2026.xlsx` |
| Virgile Moriset | 4th | 19:00:23 | `moriset_utmb2026.xlsx` |
| Joaquin Lopez | 5th | 19:06:48 | `lopez_utmb2026.xlsx` |

**Baptiste Chassagne** (2nd, 18:47:38) did not make his activity public and is
excluded. No heart-rate or power data is available for the four runners kept.

**GPX tracks** — [`utmb_2026_data/gpx/`](utmb_2026_data/gpx/), ~66,000 points per
runner (lat / lon / elevation, **no timestamps**). Used only to reconstruct the
real course geometry (local gradient) — never pace.

**Official course GPX**
([`utmb_2026_data/gpx/_official_course.gpx`](utmb_2026_data/gpx/_official_course.gpx),
UTMB World Series) — 174 km / 10,000 m of climbing, with the **25 checkpoints**
(cols and aid stations), extracted into
[`course_checkpoints.csv`](utmb_2026_data/course_checkpoints.csv).

## 3. Method

1. **Cleaning** ([`src/utmb_pacing.py`](src/utmb_pacing.py)) — parse paces and
   grade-adjusted pace into seconds/km, cadence into an integer; reconstruct
   step length (speed ÷ cadence) and per-segment time.
2. **Course geometry** ([`src/utmb_course.py`](src/utmb_course.py)) — the GPX
   tracks are resampled at a 20 m step, elevation smoothed (Savitzky-Golay,
   200 m window), local gradient derived and averaged over the four tracks.
   Each full kilometre is characterised by its **real gradient**, used to
   classify terrain (uphill / downhill / flat).
3. **Combination** ([`run_where_why.py`](run_where_why.py), `build()`) — rescale
   each segment's time to the official finish time, compute the cumulative gap
   to the winner km by km, the grade-adjusted pace gap (slope neutralised) by
   terrain type and by race third, and the descent mechanics (cadence / step
   length vs Dhiman). Aid-station kilometres and gap spikes above 80 s/km
   (stops / falls unrelated to running) are excluded.
4. **Export** ([`make_post_figures.py`](make_post_figures.py)) — assemble that
   into a single workbook, `post_figures/tableau_data.xlsx`, one sheet per
   figure, ready to open in Tableau Public.

## 4. How the figures are built

The four figures are built in Tableau Public from `post_figures/tableau_data.xlsx`.
The full workbook is inspectable and downloadable from the Tableau Public link
above. In short:

| Figure | Sheet(s) | Structure |
|---|---|---|
| **1 — Time lost along the course** | `fig1_time_lost`, `fig1_elevation`, `fig1_aid_stations` | Two stacked panels sharing the km axis. Top: elevation profile (area) with aid stations as red dots labelled by name. Bottom: `time_lost_min_smooth` vs km, one line per runner, y-axis reversed. |
| **2 — Deficit split by terrain** | `fig2_by_terrain` | Stacked area, one panel per runner (`runner` on rows). `cum_time_lost_min` vs km, colour = `terrain` (downhill / uphill / flat). |
| **3 — GAP deficit by terrain and race third** | `fig3_speed_deficit` | Grouped bars, one panel per terrain. X = `race_third` then `runner`, Y = `pace_deficit_s_per_km`, colour = runner. `race_third = "whole race"` filtered out. |
| **4 — Step rate vs step length on descents** | `fig4_descent_mechanics` | Scatter. X = `cadence_gap_ppm`, Y = `stride_gap_cm`, mark = circle, colour = runner, size = `descent_gap_s_per_km`. Reference lines at x = 0 and y = 0 (the winner). |

Runner colours are consistent across figures: Olson blue, Moriset red, Lopez
green, Dhiman grey.

## 5. Limitations

- **Sample**: 4 runners, one edition — no statistical scope.
- Baptiste Chassagne (2nd) is excluded: his Strava activity is private.
- **Step length is not measured**: it is reconstructed (speed ÷ cadence) from
  the speed and cadence columns alone.
- Each runner's kilometre markers do not line up exactly with the official
  course distance; every figure uses a common, rescaled kilometre axis rather
  than each runner's raw split numbers.
- Two runners (Olson, Moriset) have **elapsed-time** splits (stops included),
  two (Dhiman, Lopez) have **moving-time** splits. Comparisons use grade-adjusted
  pace, aid-station kilometres removed, to neutralise this.
- **No heart-rate or power data**: cadence and step length are the deepest
  signal this data allows on running mechanics.
- `Pace` and `grade-adjusted pace` are **outputs of Strava's algorithm** (its
  slope-cost model is not public): taken as given.

## 6. Repository layout

```
.
├── README.md
├── requirements.txt
├── run_where_why.py            # build(): combines Strava splits + GPX geometry
├── make_post_figures.py        # exports post_figures/tableau_data.xlsx
├── src/
│   ├── utmb_pacing.py          # Strava splits: loading, parsing, calculations
│   └── utmb_course.py          # GPX tracks: real profile, per-km gradient
├── utmb_2026_data/
│   ├── *_utmb2026.xlsx         # 4 kilometre-by-kilometre Strava splits
│   ├── gpx/*.gpx               # 4 GPS tracks (no timestamps) + official course
│   └── course_checkpoints.csv  # aid stations & cols
└── post_figures/
    └── tableau_data.xlsx       # data for the 4 figures, one sheet each
```

## 7. Reproduce

```bash
pip install -r requirements.txt
python make_post_figures.py
```

Regenerates `post_figures/tableau_data.xlsx` from the raw data in
`utmb_2026_data/` alone. That file opens directly in Tableau Public to rebuild
the four figures.

---

_Data: the runners' public Strava activities. Independent analysis, not
affiliated with UTMB, Strava or the athletes._
