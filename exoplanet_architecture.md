# Exoplanet Transit Detection Pipeline — Implementation Architecture

## 1. Problem Statement

Build a pipeline that takes raw Kepler/TESS light curves, removes noise and stellar
variability, detects repeating transit-like dips, classifies which are likely real
planets, and displays candidates (including multi-planet systems) on a dashboard
with confidence scores.

---

## 2. System Overview

```
[Data Ingestion] -> [Preprocessing / Detrending] -> [Transit Search (BLS)]
      -> [Feature Extraction] -> [Classifier] -> [Multi-planet iterative search]
      -> [Backend API] -> [Frontend Dashboard]
```

Two-person split:
- **Person A**: Data ingestion, preprocessing, BLS search, multi-planet loop
- **Person B**: Feature extraction, classifier training, backend API, frontend dashboard

---

## 3. Dataset

### Primary sources
- **Kepler / TESS light curves**: pulled via `lightkurve` (wraps MAST archive access)
  - Use **PDCSAP flux** (Pre-search Data Conditioning Simple Aperture Photometry) —
    NASA's pipeline already removes a lot of instrumental systematics, saving
    preprocessing time
- **NASA Exoplanet Archive — Cumulative KOI (Kepler Object of Interest) Table**
  - Contains labeled dispositions: `CONFIRMED`, `CANDIDATE`, `FALSE POSITIVE`
  - This is your **training label source** — no need to hand-label anything
  - Download as CSV: https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=cumulative

### Curated demo targets (guaranteed good results for live demo)
- **Multi-planet systems**: Kepler-90 (8 planets), TRAPPIST-1 (7 planets), Kepler-11
- **Clean single-planet confirmed**: Kepler-10b
- **Known false positive** (for classifier demo): pick one flagged `FALSE POSITIVE`
  in the KOI table with an eclipsing-binary-like signature

### Data fetch example
```python
import lightkurve as lk

search_result = lk.search_lightcurve("Kepler-90", mission="Kepler")
lc_collection = search_result.download_all()
lc = lc_collection.stitch()  # combine quarters into one light curve
```

---

## 4. Preprocessing / Detrending

**Goal**: remove stellar variability and instrumental trends while preserving
short-duration transit dips.

### Steps
1. **Remove NaNs / bad quality flags**
   ```python
   lc = lc.remove_nans().remove_outliers(sigma=5)
   ```
2. **Detrend stellar variability**
   - Use `wotan` (biweight or spline flattening) or `lightkurve`'s built-in `.flatten()`
   ```python
   flat_lc = lc.flatten(window_length=401)  # tune window to avoid eating transits
   ```
   - Window length should be **much longer** than expected transit duration but
     short enough to track stellar rotation/variability
3. **Sigma-clip outliers** post-detrend (cosmic ray hits, sudden pixel sensitivity dropouts)
4. **Normalize flux** to median = 1.0

### Library choices
- `lightkurve` — data access + basic detrending + plotting
- `wotan` — more robust detrending (biweight filter handles stellar variability better than simple median filters)
- `astropy` — time series utilities, BLS implementation

---

## 5. Transit Search (Period Finding)

### Method: Box Least Squares (BLS)
BLS searches over a grid of candidate periods, phase-folds the light curve at
each, and fits a box-shaped dip model, returning the period/depth/duration
combination that best matches a transit signal.

```python
from astropy.timeseries import BoxLeastSquares

bls = BoxLeastSquares(flat_lc.time.value, flat_lc.flux.value)
periodogram = bls.autopower(0.05)  # duration grid in days
best_period = periodogram.period[np.argmax(periodogram.power)]
best_t0 = periodogram.transit_time[np.argmax(periodogram.power)]
best_duration = periodogram.duration[np.argmax(periodogram.power)]
```

Alternative: `transitleastsquares` (TLS) — more accurate transit shape model
(accounts for limb darkening), slower. Use BLS for speed during the hackathon;
mention TLS as a "future work" upgrade in the presentation.

### Multi-planet iterative search
1. Run BLS on the flattened light curve → strongest period = planet 1
2. **Mask out** the in-transit points for planet 1 from the light curve
3. Re-run BLS on the residual light curve → planet 2
4. Repeat 2–3 times (diminishing returns / noise floor after that for a hackathon scope)

```python
def iterative_bls_search(time, flux, n_planets=3):
    candidates = []
    flux_residual = flux.copy()
    for i in range(n_planets):
        bls = BoxLeastSquares(time, flux_residual)
        pg = bls.autopower(0.05)
        best_idx = np.argmax(pg.power)
        period = pg.period[best_idx]
        t0 = pg.transit_time[best_idx]
        duration = pg.duration[best_idx]
        power = pg.power[best_idx]
        candidates.append({
            "period": period, "t0": t0,
            "duration": duration, "power": power
        })
        # mask this transit's in-transit points before next iteration
        mask = bls.transit_mask(time, period, duration, t0)
        flux_residual[mask] = np.nanmedian(flux_residual)
    return candidates
```

---

## 6. Feature Extraction (for the classifier)

For each BLS candidate, extract features that distinguish real planets from
false positives:

| Feature | Description |
|---|---|
| `period` | Orbital period (days) |
| `duration` | Transit duration (hours) |
| `depth` | Transit depth (fractional flux) |
| `snr` | Signal-to-noise ratio of the detection |
| `odd_even_depth_diff` | Depth difference between odd/even-numbered transits — large diff suggests eclipsing binary |
| `secondary_eclipse_depth` | Depth at phase 0.5 (opposite side of orbit) — real planets should show ~0, stellar companions show a detectable dip |
| `transit_shape_symmetry` | Ingress vs egress duration symmetry |
| `num_transits_observed` | More observed transits = more confidence |
| `stellar_radius` (if available from catalog) | Used to sanity check implied planet radius |

Odd-even and secondary eclipse checks:
```python
# Fold at period, split into odd/even transit numbers, compare depths
# Fold at period but centered on phase 0.5 to check secondary eclipse depth
```

---

## 7. Model / Classifier

### Approach: gradient-boosted trees on extracted features (NOT raw light curve CNN — too slow to train well in hackathon time)

- **Model**: `XGBoost` or `LightGBM` classifier
- **Training data**: NASA KOI cumulative table — extract the same features
  (period, duration, depth, SNR, odd-even diff, etc. — many of these are
  already columns in the KOI table itself, e.g. `koi_period`, `koi_duration`,
  `koi_depth`, `koi_model_snr`)
- **Labels**: collapse `CONFIRMED` + `CANDIDATE` → 1 (planet-like), `FALSE POSITIVE` → 0
  (or do 3-class if time allows)
- **Output**: probability score → this is your "confidence score" for the dashboard

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y)

clf = xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1)
clf.fit(X_train, y_train)

confidence_scores = clf.predict_proba(X_new)[:, 1]  # probability of being a real planet
```

### Why not a CNN on raw folded light curves
- Legitimate approach (this is what Google's AstroNet does), but requires more
  data engineering and training time than a hackathon allows
- Mention it in the presentation as a "next step" to show awareness of the
  state of the art

---

## 8. Backend

### Stack
- **Python + FastAPI** — lightweight, async, easy to wire ML code directly in
- Endpoints:
  - `POST /analyze` — takes a target name (e.g. "Kepler-90"), runs the full
    pipeline (fetch → detrend → BLS → features → classify), returns candidates
  - `GET /candidates/{target}` — cached results for known demo targets (precompute
    these ahead of time so the live demo doesn't wait on live data fetch/BLS,
    which can be slow)
  - `GET /lightcurve/{target}` — raw + phase-folded light curve data for plotting

### Precompute strategy (important for demo reliability)
Run the full pipeline **ahead of time** on your curated demo targets and cache
results as JSON. Live-run the pipeline only as a bonus "type in any star name"
feature if time/network allows — don't depend on live MAST queries during the
actual presentation.

```
/cache
  kepler-90.json
  trappist-1.json
  kepler-10b.json
  false_positive_example.json
```

---

## 9. Frontend Dashboard

### Stack recommendation
- **Streamlit** — fastest to build, good for hackathon timelines, Python-native
  (no separate frontend/backend split needed if you want to save time — can
  call your pipeline functions directly)
- Alternative if you want a more "product" feel: React + a simple FastAPI backend,
  using Plotly.js or Recharts for the light curve plots

### Key views
1. **Target search / selector** — dropdown or search box for star name
2. **Light curve viewer**
   - Raw flux vs time
   - Detrended flux vs time
   - Phase-folded view at detected period (this is the "money shot" — clean
     folded transit dip is visually convincing)
3. **Candidate list / table**
   - Star name, period, depth, duration, confidence score, disposition (planet/false positive)
   - Sort/filter by confidence score
4. **Multi-planet system view**
   - Show all detected planets for a system on one page (e.g. Kepler-90 or
     TRAPPIST-1), each with its own phase-folded plot and confidence score
   - This directly demonstrates the "stars that host more than one planet" requirement

### Streamlit skeleton
```python
import streamlit as st
import plotly.graph_objects as go

st.title("Exoplanet Transit Candidate Dashboard")

target = st.selectbox("Select target", ["Kepler-90", "TRAPPIST-1", "Kepler-10"])
data = load_cached_results(target)  # from /cache JSON

for planet in data["candidates"]:
    st.subheader(f"Candidate: Period = {planet['period']:.2f} days")
    st.metric("Confidence Score", f"{planet['confidence']*100:.1f}%")
    fig = go.Figure(data=go.Scatter(
        x=planet["phase"], y=planet["flux"], mode="markers"
    ))
    st.plotly_chart(fig)
```

---

## 10. Timeline Suggestion (pre-hackathon prep + hackathon day)

### Before hackathon (tonight/tomorrow prep)
- [ ] Confirm library installs (`lightkurve`, `wotan`, `astropy`, `xgboost`, `streamlit`)
- [ ] Download KOI cumulative table CSV
- [ ] Pull + cache light curves for 3–4 demo targets
- [ ] Sketch dashboard wireframe for the slides

### Hackathon day
- **Hours 0–2**: Data pipeline (fetch, detrend) working end-to-end on one target
- **Hours 2–4**: BLS search + multi-planet iterative loop working
- **Hours 4–6**: Feature extraction + classifier trained on KOI table
- **Hours 6–8**: Backend wiring + cache precompute for demo targets
- **Hours 8–10**: Dashboard built, connected to cached results
- **Last hours**: Polish, rehearse demo flow, prepare fallback (screenshots/video)
  in case live demo breaks

---

## 11. Known Limitations to Preempt in Q&A

- BLS assumes a box-shaped transit; doesn't model limb darkening as accurately
  as `transitleastsquares` — acceptable tradeoff for hackathon speed
- Classifier trained on Kepler-labeled data may not generalize perfectly to
  TESS light curves (different noise characteristics, shorter baselines) —
  worth mentioning as a validity caveat
- Multi-planet iterative search (mask-and-research) can miss resonant or
  weak signals after 2–3 iterations — real pipelines (e.g. Kepler's own DR25)
  use more sophisticated joint-fitting
- No true uncertainty quantification on confidence scores — it's a point
  probability from the classifier, not a calibrated statistical significance

---

## 12. Key Libraries Reference

| Purpose | Library |
|---|---|
| Data access | `lightkurve` |
| Detrending | `wotan`, `lightkurve.flatten()` |
| Transit search | `astropy.timeseries.BoxLeastSquares`, `transitleastsquares` |
| Classifier | `xgboost` or `lightgbm` |
| Backend | `fastapi` |
| Frontend | `streamlit` (or React + Plotly) |
| Labeled training data | NASA Exoplanet Archive — Cumulative KOI Table |
