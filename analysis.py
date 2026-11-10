"""Carbon exposure scoring for Nifty 50 companies from SEBI BRSR (FY2023-24, FY2022-23).

Run:  .venv/bin/python extract.py && .venv/bin/python analysis.py
Outputs: data/company_metrics.csv, data/my_model_sensitivity.csv, charts/*.png, printed findings.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).parent
CHARTS = ROOT / "charts"
CHARTS.mkdir(exist_ok=True)
CUR, PREV = "FY2023-24", "FY2022-23"

# Chart palette (dataviz skill default instance): categorical slots 1-3, text inks, surface.
NAVY, GREY, DARK = "#1f3a5f", "#9aa3ad", "#1b1f24"  # 2-colour palette: navy + neutrals
INK, INK2, GRID, SURFACE = "#1b1f24", "#5f6670", "#dfe2e6", "#ffffff"
GRADE_STYLE = {"Acceptable": (DARK, "o"), "Neutral": (GREY, "s"), "Brown exposure": (NAVY, "^")}
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})

# ---------------------------------------------------------------- 1. load + QA
raw = pd.read_csv(ROOT / "data" / "brsr_emissions.csv")
raw["total_tco2e"] = raw.scope1_tco2e + raw.scope2_tco2e
# JIO Financial listed Aug 2023: its FY2022-23 BRSR columns are all zero, not a real year.
raw = raw[~((raw.symbol == "JIOFIN") & (raw.fy == PREV))]

wide = raw.pivot(index="symbol", columns="fy")
yoy_emis = wide["total_tco2e"][CUR] / wide["total_tco2e"][PREV]
yoy_rev = wide["revenue_cr"][CUR] / wide["revenue_cr"][PREV]
# ponytail: a >3x jump in a single year is a boundary/methodology/unit break, not real change.
BREAK = 3
emis_break = (yoy_emis > BREAK) | (yoy_emis < 1 / BREAK)
rev_break = (yoy_rev > BREAK) | (yoy_rev < 1 / BREAK)

df = raw[raw.fy == CUR].set_index("symbol").copy()
df["intensity"] = df.total_tco2e / df.revenue_cr                     # tCO2e per Rs crore
df["scope1_share"] = df.scope1_tco2e / df.total_tco2e
df["nonrenew_share"] = 1 - df.energy_renewable_gj / df.energy_gj
df["emissions_yoy"] = (yoy_emis - 1).where(~emis_break)
prev_int = wide["total_tco2e"][PREV] / wide["revenue_cr"][PREV]
df["intensity_yoy"] = (df.intensity / prev_int - 1).where(~emis_break & ~rev_break)
df["yoy_break"] = np.where(emis_break.reindex(df.index) | rev_break.reindex(df.index), "excluded (>3x break)", "")

# Sector-relative z-score on log10 intensity (intensity spans 5 orders of magnitude).
df["log_int"] = np.log10(df.intensity)
g = df.groupby("sector")["log_int"]
df["sector_n"] = g.transform("size")
df["sector_z"] = ((df.log_int - g.transform("mean")) / g.transform("std")).where(df.sector_n >= 3)

# ---------------------------------------------------------------- 2. Rohan's (m)y model
# Parameter -> position on the x-axis, in the deck's order: Inputs, then Transitions, then Demands.
PARAMS = [("energy_gj", "Input: total energy (GJ)", "log"),
          ("nonrenew_share", "Input: non-renewable energy share", "lin"),
          ("scope1_tco2e", "Transition: Scope 1 (direct, fossil/process)", "log"),
          ("scope2_tco2e", "Transition: Scope 2 (purchased power)", "log"),
          ("revenue_cr", "Demand: revenue from operations (Rs cr)", "log")]


def to_1_10(s, how):
    """Deck: 'each parameter normalised into one scale', 1-10. Min-max across the cohort."""
    if how == "rank":
        return 1 + 9 * (s.rank() - 1) / (s.count() - 1)
    if how == "log":
        s = np.log10(s.clip(lower=1e-9) + 1)
    return 1 + 9 * (s - s.min()) / (s.max() - s.min())


def my_model(d, scale="default", params=PARAMS, band=0.25):
    """Fit y = m*x + c through the 1-10 parameter values; grade by slope m and intercept c."""
    X = np.arange(1, len(params) + 1)
    Y = pd.DataFrame({c: to_1_10(d[c], scale if scale != "default" else how) for c, _, how in params})
    fits = np.array([np.polyfit(X, row, 1) for row in Y.values])
    out = pd.DataFrame({"m": fits[:, 0], "y": fits[:, 1]}, index=d.index)
    out["grade"] = np.select([out.m > band, (out.m < -band) & (out.y > 0)],
                             ["Acceptable", "Brown exposure"], "Neutral")
    return out, Y


cohort = df.dropna(subset=[c for c, _, _ in PARAMS] + ["intensity"]).copy()
my, Y = my_model(cohort)
cohort = cohort.join(my)
df = df.join(my)

# ---------------------------------------------------------------- 3. compare with plain intensity
rho, p = spearmanr(cohort.m, cohort.intensity)
cohort["rank_intensity"] = cohort.intensity.rank()                   # 1 = cleanest
cohort["rank_my"] = (-cohort.m).rank()                               # 1 = steepest upward slope (best)
cohort["rank_gap"] = cohort.rank_my - cohort.rank_intensity
terc = pd.qcut(cohort.intensity, 3, labels=["low", "mid", "high"])
disagree = cohort[((terc == "high") & (cohort.grade == "Acceptable")) | ((terc == "low") & (cohort.grade == "Brown exposure"))]

# Sensitivity: scale choice, grading band, and dropping a parameter.
sens = []
for name, kw in {"default (log min-max)": {}, "linear min-max": {"scale": "lin"},
                 "percentile rank": {"scale": "rank"}, "band 0.10": {"band": 0.10}, "band 0.50": {"band": 0.50},
                 "drop non-renewable share": {"params": [q for q in PARAMS if q[0] != "nonrenew_share"]},
                 "drop energy": {"params": [q for q in PARAMS if q[0] != "energy_gj"]}}.items():
    alt, _ = my_model(cohort, **kw)
    sens.append({"variant": name, "acceptable": (alt.grade == "Acceptable").sum(),
                 "neutral": (alt.grade == "Neutral").sum(), "brown": (alt.grade == "Brown exposure").sum(),
                 "grade_changes_vs_default": (alt.grade != cohort.grade).sum(),
                 "spearman_m_vs_default": round(spearmanr(alt.m, cohort.m)[0], 3),
                 "spearman_m_vs_intensity": round(spearmanr(alt.m, cohort.intensity)[0], 3)})
sens = pd.DataFrame(sens)

# Sector mix: how much of the spread in log intensity is explained by sector alone (eta squared).
ss_tot = ((df.log_int - df.log_int.mean()) ** 2).sum()
ss_between = (df.groupby("sector").log_int.transform("mean") - df.log_int.mean()).pow(2).sum()
eta2 = ss_between / ss_tot

# ---------------------------------------------------------------- 4. save + print
cols = ["company", "sector", "revenue_cr", "scope1_tco2e", "scope2_tco2e", "total_tco2e", "intensity",
        "scope1_share", "nonrenew_share", "emissions_yoy", "intensity_yoy", "yoy_break", "sector_z", "m", "y", "grade"]
df[cols].sort_values("intensity").to_csv(ROOT / "data" / "company_metrics.csv", float_format="%.4g")
sens.to_csv(ROOT / "data" / "my_model_sensitivity.csv", index=False)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
print(f"Companies with FY24 data: {len(df)}; with revenue (intensity): {df.intensity.notna().sum()}; "
      f"in (m)y cohort: {len(cohort)}; with clean YoY: {df.intensity_yoy.notna().sum()}")
print(f"Total FY24 Scope 1+2: {df.total_tco2e.sum()/1e6:.1f} Mt; top 5 share: "
      f"{df.total_tco2e.nlargest(5).sum()/df.total_tco2e.sum():.1%} ({', '.join(df.total_tco2e.nlargest(5).index)})")
print(f"Intensity median {df.intensity.median():.2f}, min {df.intensity.min():.3f} ({df.intensity.idxmin()}), "
      f"max {df.intensity.max():.1f} ({df.intensity.idxmax()}); max/min = {df.intensity.max()/df.intensity.min():,.0f}x")
print(f"Sector explains eta^2 = {eta2:.1%} of variance in log intensity")
print("\nSector medians (tCO2e / Rs cr):")
print(df.groupby("sector").agg(n=("intensity", "size"), median_intensity=("intensity", "median"),
                               scope1_share=("scope1_share", "median")).sort_values("median_intensity").round(2))
print(f"\nScope 1 share median {df.scope1_share.median():.1%}; Scope 2 > Scope 1 for "
      f"{(df.scope1_share < .5).sum()} of {len(df)}")
print(f"YoY (clean pairs): median emissions change {df.emissions_yoy.median():+.1%}, median intensity change "
      f"{df.intensity_yoy.median():+.1%}; intensity fell for {(df.intensity_yoy < 0).sum()} of {df.intensity_yoy.notna().sum()}")
print("Excluded from YoY:", ", ".join(df.index[df.yoy_break != ""]))
print("\nSector z-score outliers (|z| >= 1.2):")
print(df.loc[df.sector_z.abs() >= 1.2, ["sector", "intensity", "sector_z"]].sort_values("sector_z").round(2))
print(f"\n(m)y grades: {cohort.grade.value_counts().to_dict()}")
print(f"Spearman(m, intensity) = {rho:.3f} (p = {p:.2g}, n = {len(cohort)})")
print("Grade disagrees with intensity tercile:")
print(disagree[["sector", "intensity", "m", "y", "grade"]].round(2))
print("Largest rank gaps (positive = (m)y ranks it worse than intensity does):")
print(cohort.reindex(cohort.rank_gap.abs().sort_values(ascending=False).index)
      [["sector", "intensity", "rank_intensity", "m", "rank_my", "rank_gap"]].head(6).round(2))
print("\nSensitivity:\n", sens.to_string(index=False))
fin = df[df.sector == "Financial Services"]
print(f"\nFinancial Services: {len(fin)} cos, median intensity {fin.intensity.median():.2f}, "
      f"grades {fin.grade.value_counts().to_dict()}")

# ---------------------------------------------------------------- 5. charts
# 5a. Intensity by sector: dot per company on a log axis, sector median tick.
order = df.groupby("sector").intensity.median().sort_values().index
fig, ax = plt.subplots(figsize=(9, 6))
for i, s in enumerate(order):
    v = df[df.sector == s].intensity.dropna()
    ax.scatter(v, [i] * len(v), s=40, color=NAVY, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.plot([v.median()] * 2, [i - .3, i + .3], color=INK, lw=2, zorder=4)
ax.set_xscale("log")
ax.set_yticks(range(len(order)), [f"{s} (n={(df.sector == s).sum()})" for s in order])
ax.grid(axis="x", color=GRID, lw=.8)
ax.set_xlabel("Scope 1+2 intensity, tCO2e per Rs crore of revenue (log scale)")
ax.set_title(f"Emissions intensity spans {df.intensity.max()/df.intensity.min():,.0f}x across the Nifty 50, "
             f"mostly by sector\nFY2023-24 BRSR, dot = company, bar = sector median", loc="left", fontsize=11)
fig.tight_layout()
fig.savefig(CHARTS / "1_intensity_by_sector.png", dpi=160)

# 5b. Sector-relative outliers: z-score within sector (sectors with >= 3 companies).
z = df.sector_z.dropna().sort_values()
fig, ax = plt.subplots(figsize=(8, 7))
ax.barh(z.index, z, color=[NAVY if v > 0 else GREY for v in z], height=.7)
ax.axvline(0, color=INK2, lw=1)
ax.grid(axis="x", color=GRID, lw=.8)
ax.set_xlabel("Sector-relative z-score of log intensity  (left = cleaner than peers, right = dirtier)")
ax.set_title("Who is dirty for their sector? Sector z-score, FY2023-24\n(only sectors with 3+ companies)",
             loc="left", fontsize=11)
fig.tight_layout()
fig.savefig(CHARTS / "2_sector_relative_outliers.png", dpi=160)

# 5c. (m)y slope vs intensity.
fig, ax = plt.subplots(figsize=(8, 6))
for grade, (c, mk) in GRADE_STYLE.items():
    d = cohort[cohort.grade == grade]
    ax.scatter(d.intensity, d.m, color=c, marker=mk, s=55, edgecolor=SURFACE, linewidth=1.5, label=f"{grade} ({len(d)})", zorder=3)
for sym in set(cohort.intensity.nlargest(3).index) | set(cohort.rank_gap.abs().nlargest(5).index) | set(disagree.index):
    ax.annotate(sym, (cohort.intensity[sym], cohort.m[sym]), xytext=(5, 4), textcoords="offset points", fontsize=8, color=INK2)
ax.axhspan(-.25, .25, color=GRID, alpha=.6, zorder=0)
ax.set_xscale("log")
ax.grid(color=GRID, lw=.8)
ax.set_xlabel("Scope 1+2 intensity, tCO2e per Rs crore (log scale)")
ax.set_ylabel("(m)y slope m")
ax.legend(frameon=False, loc="upper right")
ax.set_title(f"The (m)y slope only partly tracks intensity: Spearman rho = {rho:.2f}\nShaded band = Neutral (|m| <= 0.25)",
             loc="left", fontsize=11)
fig.tight_layout()
fig.savefig(CHARTS / "3_my_slope_vs_intensity.png", dpi=160)

# 5d. The (m)y model itself for three real companies (deck's Company 1/2/3 view).
picks = [cohort.m.idxmax(), cohort.m.abs().idxmin(), cohort.m.idxmin()]
fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
X = np.arange(1, len(PARAMS) + 1)
for ax, sym in zip(axes, picks):
    m, c, grade = cohort.loc[sym, ["m", "y", "grade"]]
    ax.scatter(X, Y.loc[sym], color=INK, s=40, zorder=3)
    ax.plot(X, m * X + c, color=GRADE_STYLE[grade][0], lw=2)
    ax.set_xticks(X, ["Energy", "Non-RE\nshare", "Scope 1", "Scope 2", "Revenue"], fontsize=8)
    ax.set_ylim(0, 11)
    ax.grid(axis="y", color=GRID, lw=.8)
    ax.set_title(f"{sym}: (m)y = ({m:.2f}){c:.1f}\n{grade}", fontsize=10)
axes[0].set_ylabel("Normalised value (1-10)")
fig.suptitle("Rohan's (m)y model on real BRSR data: inputs and transitions, then demand", x=.01, ha="left", fontsize=11)
fig.tight_layout()
fig.savefig(CHARTS / "4_my_model_examples.png", dpi=160)

# ---------------------------------------------------------------- self-check
assert to_1_10(pd.Series([1.0, 10.0, 100.0]), "lin").tolist()[0] == 1 and to_1_10(pd.Series([1.0, 100.0]), "lin").iloc[-1] == 10
assert np.allclose(np.polyfit(X, [1, 2, 3, 4, 5], 1), [1, 0])  # slope/intercept convention
assert df.loc["NTPC", "scope1_tco2e"] > 1e8, "corrections.csv not applied"
print("\ncharts written:", ", ".join(p.name for p in sorted(CHARTS.glob("*.png"))))
