# Exoplanet Transit Lab

A demo-ready vertical slice of the architecture in
`exoplanet_architecture.md`: light-curve preprocessing, an iterative transit
search, candidate feature extraction and scoring, cached demo targets, a
FastAPI service, and a Streamlit dashboard.

The bundled targets use deterministic synthetic light curves shaped around
well-known systems. This keeps the demo fast and reliable without pretending
that generated points are archive observations. Optional `lightkurve` support
can fetch a real Kepler or TESS target when network access is available.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
streamlit run dashboard.py
```

Open the API in a second terminal if desired:

```powershell
uvicorn exoplanet_lab.api:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for the interactive API reference.

## Optional real archive support

```powershell
pip install -e ".[science]"
```

With `lightkurve` installed, `POST /analyze` can fetch a non-demo target by
name when `use_archive` is `true`. For reproducible judging, generate the local
demo cache before the event:

```powershell
python scripts/generate_demo_cache.py
```

To analyze a real target from PowerShell, send a request such as:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/analyze `
  -ContentType 'application/json' `
  -Body '{"target":"K00752.01","use_archive":true,"mission":"Kepler","max_files":4}'
```

The resolver converts a KOI like `K00752.01` into its NASA `kepid`, then
queries MAST through Lightkurve with `KIC <kepid>`. The trained classifier is
used for the returned candidate scores. A KOI name and a KIC name are not the
same identifier: the KOI labels a signal, while the KIC labels its host star.

## Web frontend

`web/` is a standalone Vite + React + TypeScript app (night-sky indigo/violet
theme) that talks to the FastAPI service directly — it is not a Streamlit
alternative, it's a second, more presentation-ready client for the same API.

```powershell
uvicorn exoplanet_lab.api:app --reload
```

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. It reads `VITE_API_BASE` (defaults to
`http://127.0.0.1:8000`) if the API runs elsewhere; set it in `web/.env.local`.

## API surface

- `GET /targets` — available cached demo targets
- `GET /candidates/{target}` — complete analysis result
- `GET /lightcurve/{target}` — raw and detrended series
- `POST /analyze` — analyze provided time/flux arrays, a demo target, or an
  archive target when `use_archive: true` and `lightkurve` is installed
- `GET /resolve/{target}` — show the KOI → KIC host mapping used for MAST
- `GET /health` — readiness check

## Tests

The core suite uses only Python's standard test runner plus NumPy:

```powershell
python -m unittest discover -s tests -v
```

## Train the KOI classifier

The runnable notebook downloads labeled KOIs through NASA's current TAP
service, makes star-grouped train/validation/test splits, trains calibrated
gradient-boosted trees, evaluates the untouched holdout set, and writes a model
bundle to `models/`.

```powershell
.venv\Scripts\python.exe -m pip install -r notebooks/requirements.txt
.venv\Scripts\python.exe -m jupyter lab notebooks/train_koi_classifier.ipynb
```

Use **Run All Cells**. The first run caches the selected archive columns at
`data/koi_cumulative_training.csv`; future runs reuse that file unless the
notebook's `REFRESH_DATA` switch is enabled.

For a one-command headless run instead of opening Jupyter:

```powershell
.venv\Scripts\python.exe scripts/train_koi_classifier.py
```

After training, predict on a real MAST light curve from the command line:

```powershell
.venv\Scripts\python.exe scripts/predict_target.py K00752.01
```

Print the saved holdout metrics for a presentation:

```powershell
.venv\Scripts\python.exe scripts/show_metrics.py
```

Use `--blind` to search the full period range rather than using the NASA KOI
catalog period as a confirmation hint. The same option is available in the
Streamlit real-data mode and the API field `use_catalog_period_hint`.

## Current scope

The confidence model is deliberately transparent: a calibrated-looking
heuristic combines SNR, event count, depth, odd/even consistency, secondary
eclipse evidence, and shape symmetry. Real archive analysis now loads the
calibrated model exported by the notebook; the heuristic remains as a fallback
when the model artifact is absent. Scores are rankings, not planet
confirmations.
