"""Run every sql/*.sql on DuckDB, save results to sql/results/, and assert they match the Python pipeline.

Run:  .venv/bin/python run_sql.py   (after analysis.py, which writes data/company_metrics.csv)
"""
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
os.chdir(ROOT)  # SQL files read data/*.csv by relative path
OUT = ROOT / "sql" / "results"
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

res = {}
for f in sorted((ROOT / "sql").glob("*.sql")):
    res[f.stem] = r = duckdb.sql(f.read_text()).df()
    r.to_csv(OUT / f"{f.stem}.csv", index=False)
    print(f"\n=== {f.name} ({len(r)} rows) ===\n{r.head(12).to_string(index=False)}")

# ---------------------------------------------------------------- asserts vs analysis.py outputs
py = pd.read_csv(ROOT / "data" / "company_metrics.csv").set_index("symbol")
close = lambda a, b: np.allclose(a, b, rtol=1e-3, equal_nan=True)  # company_metrics.csv is saved at 4 sig. figs

i = res["01_intensity"].set_index("symbol")
assert len(i) == 49 and close(i.intensity, py.intensity.reindex(i.index)), "intensity mismatch"
assert close(i.scope1_share, py.scope1_share.reindex(i.index)), "scope1_share mismatch"
assert round(i.intensity.median(), 2) == 5.23 and round(i.intensity.max() / i.intensity.min()) == 144820

s = res["02_sector_rank"]
py_med = py.groupby("sector").intensity.median()
assert close(s.sector_median_intensity, py_med.reindex(s.sector)), "sector median mismatch"
fin = s[s.sector == "Financial Services"]
assert round(fin.sector_median_intensity.iloc[0], 2) == 0.74 and len(fin) == 12

y = res["03_yoy"].set_index("symbol")
assert close(y.emissions_yoy, py.emissions_yoy.reindex(y.index)), "emissions YoY mismatch"
assert close(y.intensity_yoy, py.intensity_yoy.reindex(y.index)), "intensity YoY mismatch"
assert sorted(y.index[y.yoy_break]) == ["APOLLOHOSP", "AXISBANK", "SBILIFE", "TATACONSUM"]
r0 = y.iloc[0]
assert r0.n_intensity_pairs == 44 and round(r0.median_intensity_yoy, 3) == -0.093 and r0.n_intensity_fell == 34
# README: "median absolute emissions rose 2.5%". analysis.py takes that median over 45 pairs (Axis's break is
# revenue-only, so its emissions YoY is kept). On the same 44 pairs as intensity it is +2.8%, not +2.5%:
# the direction holds, but "44 pairs" and "+2.5%" in the README come from slightly different samples.
assert r0.n_emissions_pairs == 45 and round(r0.median_emissions_yoy, 3) == 0.025
assert round(r0.median_emissions_yoy_same_pairs, 3) == 0.028

c = res["04_concentration"]
assert round(c.total_tco2e.sum() / 1e6, 1) == 675.3
assert round(c.cumulative_share.iloc[4], 3) == 0.858, "top-5 share mismatch"
assert list(c.symbol[:5]) == ["NTPC", "ULTRACEMCO", "TATASTEEL", "JSWSTEEL", "RELIANCE"]
assert 0.515 < c.share.iloc[0] < 0.525, f"NTPC share {c.share.iloc[0]:.3f}"
fin_share = c[c.sector == "Financial Services"].share.sum()
assert round(fin_share, 4) == 0.0028, f"financials share {fin_share:.4%}"

z = res["05_sector_zscore"].set_index("symbol")
assert close(z.sector_z, py.sector_z.reindex(z.index)), "sector z-score mismatch"
assert py.sector_z.notna().sum() == len(z)  # same companies scored
for sym, v in {"BSE": 2.21, "ADANIENT": -1.49, "HINDUNILVR": -1.48, "BAJAJ-AUTO": -1.34, "COALINDIA": 1.15,
               "APOLLOHOSP": 1.15, "EICHERMOT": 1.08}.items():
    assert round(z.sector_z[sym], 2) == v, f"{sym} z {z.sector_z[sym]:.3f} != README {v}"

q = res["06_data_quality"].set_index("error_type")
assert q.companies["ANY (total)"] == 9 and "other" not in q.index  # README: 9 companies with unit/value errors

print(f"\nAll SQL-vs-Python asserts passed. Results in {OUT.relative_to(ROOT)}/")
