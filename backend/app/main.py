"""Wind forecast vs actual API (Elexon FUELHH / WINDFOR), Jan 2026 delivery days."""
import os
from functools import lru_cache
import httpx, numpy as np, pandas as pd
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
CACHE = os.environ.get("CACHE_DIR", "/tmp/cache")
BUNDLED = os.path.join(os.path.dirname(__file__), "data")
MAX_H = 48  # keep forecasts published up to 48h before target
app = FastAPI(title="Wind forecast monitor")

def _get(ds, params):
    r = httpx.get(f"{BASE}/{ds}/stream", params=params, timeout=90)
    r.raise_for_status()
    return r.json()

def _chunks(start, end, step):
    t = pd.Timestamp(start, tz="UTC")
    while t < pd.Timestamp(end, tz="UTC"):
        yield t, min(t + step, pd.Timestamp(end, tz="UTC"))
        t += step

@lru_cache
def data():
    """Returns (actuals[startTime, actual], forecasts[startTime, publishTime, forecast, horizon_h])."""
    ba, bf = f"{BUNDLED}/act.csv.gz", f"{BUNDLED}/fc.csv.gz"
    if os.path.exists(ba) and os.path.exists(bf):  # snapshot bundled in repo (used on Vercel)
        a = pd.read_csv(ba); f = pd.read_csv(bf)
        for df_, cols in ((a, ["startTime"]), (f, ["startTime", "publishTime"])):
            for c in cols: df_[c] = pd.to_datetime(df_[c], utc=True)
        return a, f
    fa, ff = f"{CACHE}/act.pkl", f"{CACHE}/fc.pkl"
    if os.path.exists(fa) and os.path.exists(ff):
        return pd.read_pickle(fa), pd.read_pickle(ff)
    os.makedirs(CACHE, exist_ok=True)
    act = []
    for s, e in _chunks("2026-01-01", "2026-02-01", pd.Timedelta(days=7)):
        act += _get("FUELHH", {"settlementDateFrom": s.date().isoformat(),
                               "settlementDateTo": (e - pd.Timedelta(days=1)).date().isoformat(),
                               "fuelType": "WIND", "format": "json"})
    a = pd.DataFrame(act)
    a = a[a.fuelType == "WIND"]
    a = pd.DataFrame({"startTime": pd.to_datetime(a.startTime, utc=True), "actual": a.generation.astype(float)})
    a = a.drop_duplicates("startTime")
    fc = []
    for s, e in _chunks("2025-12-29", "2026-02-01", pd.Timedelta(days=2)):
        fc += _get("WINDFOR", {"publishDateTimeFrom": s.isoformat(), "publishDateTimeTo": e.isoformat(), "format": "json"})
    f = pd.DataFrame(fc)
    f = pd.DataFrame({"startTime": pd.to_datetime(f.startTime, utc=True),
                      "publishTime": pd.to_datetime(f.publishTime, utc=True),
                      "forecast": f.generation.astype(float)})
    f["horizon_h"] = (f.startTime - f.publishTime).dt.total_seconds() / 3600
    f = f[(f.horizon_h >= 0) & (f.horizon_h <= MAX_H)]
    a.to_pickle(fa); f.to_pickle(ff)
    return a, f

def day_ahead(cutoff_hour: float):
    """Per target time: latest forecast published at/before (delivery day - 1 day + cutoff_hour) UTC.
    UK is on GMT in January so UTC == local time."""
    a, f = data()
    f = f.copy()
    f["cutoff"] = f.startTime.dt.floor("D") - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    f = f[f.publishTime <= f.cutoff].sort_values("publishTime").groupby("startTime").tail(1)
    f = f[(f.startTime >= "2026-01-01") & (f.startTime < "2026-02-01")]
    return f.merge(a, on="startTime", how="left").sort_values("startTime")

def metrics(df):
    d = df.dropna(subset=["actual", "forecast"])
    if d.empty: return {}
    e = d.forecast - d.actual; ae = e.abs()
    nz = d.actual > 100
    return {"n": int(len(d)), "mae": ae.mean(), "rmse": float(np.sqrt((e**2).mean())), "bias": e.mean(),
            "mape": float((ae[nz] / d.actual[nz]).mean() * 100), "p50_abs": ae.quantile(.5),
            "p90_abs": ae.quantile(.9), "p95_abs": ae.quantile(.95), "max_abs": ae.max()}

def out(df):
    df = df.copy()
    for c in df.select_dtypes("datetimetz"): df[c] = df[c].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.replace({np.nan: None}).to_dict("records")

@app.get("/api/forecast")
def forecast(date: str = "2026-01-15", cutoff_hour: float = Query(9.0, ge=0, le=23.5)):
    """Day-ahead view for one delivery day: forecast known at cutoff on D-1, plus actuals (if available)."""
    df = day_ahead(cutoff_hour)
    df = df[df.startTime.dt.strftime("%Y-%m-%d") == date]
    return {"rows": out(df[["startTime", "publishTime", "forecast", "actual"]]), "metrics": metrics(df)}

@app.get("/api/accuracy")
def accuracy(cutoff_hour: float = 9.0, start: str = "2026-01-01", end: str = "2026-01-31"):
    df = day_ahead(cutoff_hour)
    df = df[(df.startTime >= start) & (df.startTime < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))].copy()
    df["day"] = df.startTime.dt.strftime("%Y-%m-%d"); df["hour"] = df.startTime.dt.hour
    daily = [{"day": k, **metrics(g)} for k, g in df.groupby("day")]
    hourly = [{"hour": int(k), **metrics(g)} for k, g in df.groupby("hour")]
    d = df.dropna(subset=["actual"]); err = (d.forecast - d.actual)
    hist = np.histogram(err, bins=20) if len(err) else ([], [])
    return {"overall": metrics(df), "daily": daily, "by_hour": hourly,
            "error_hist": [{"bin": float((hist[1][i] + hist[1][i+1]) / 2), "count": int(c)} for i, c in enumerate(hist[0])]}

@app.get("/api/horizon")
def horizon(start: str = "2026-01-01", end: str = "2026-01-31"):
    """Error vs forecast lead time (all publishes, 0-48h before target)."""
    a, f = data()
    d = f.merge(a, on="startTime")
    d = d[(d.startTime >= start) & (d.startTime < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))].copy()
    d["lead"] = (d.horizon_h // 4 * 4).astype(int)
    return [{"lead_h": int(k), **metrics(g)} for k, g in d.groupby("lead")]

if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True))
