"""Run once: downloads Jan 2026 data from Elexon and saves a snapshot into backend/app/data/ (bundled for Vercel)."""
import os
os.environ.setdefault("CACHE_DIR", "./cache")
from app.main import data, BUNDLED
a, f = data()
os.makedirs(BUNDLED, exist_ok=True)
a.to_csv(f"{BUNDLED}/act.csv.gz", index=False)
f.to_csv(f"{BUNDLED}/fc.csv.gz", index=False)
print("saved", len(a), "actual rows,", len(f), "forecast rows")
