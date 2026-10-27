# Wind forecast monitor (UK day-ahead)
AI assistance (Claude) was used to scaffold this code. Live app: <ADD HEROKU/RENDER URL>

## Layout
- `backend/app/main.py` – FastAPI: pulls Elexon FUELHH (WIND) and WINDFOR, caches, computes day-ahead selection + metrics
- `frontend/src/App.jsx` – React/Recharts dashboard (Vite)
- `Dockerfile` – multi-stage: builds React, serves it from FastAPI on one port

## Run
`docker build -t wind . && docker run -p 8000:8000 wind` -> http://localhost:8000 (first request downloads Jan 2026 data, ~1 min)
Dev: `uvicorn app.main:app --reload` in backend/, `npm run dev` in frontend/.

## Method
- Decision rule: for each target half-hour, use the latest forecast with publishTime <= (delivery day - 1d + cutoff hour, default 09:00 UTC; UK = GMT in Jan). Cutoff is adjustable in the UI.
- Metrics: MAE, RMSE, bias, MAPE (actual>100MW), P50/P90/P95/max absolute error, by day, by hour, by forecast lead time (0-48h).
- Deploy: Heroku container stack (`heroku stack:set container`, `heroku container:push web`). Vercel does not run Docker.

## Vercel deployment
Vercel cannot run Docker, so it uses `vercel.json` + `api/index.py` (FastAPI as a serverless function) and a bundled data snapshot
(`backend/app/data/*.csv.gz`, created by `cd backend && python prefetch.py`) so no Elexon calls are made at runtime. Docker remains the local/container path.
