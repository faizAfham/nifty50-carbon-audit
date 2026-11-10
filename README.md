# Carbon exposure scoring for the Nifty 50 (SEBI BRSR, FY2023-24)

Extends the (m)y model concept by Rohan Choudhary (IIT Patna), used with permission.

## The question
How carbon-intensive are India's largest listed companies, measured on their own mandatory disclosures? And does a regression-based grade (Rohan's "(m)y" slope/intercept model) say anything that plain emissions intensity doesn't?

## Data and coverage
- **Source:** SEBI Business Responsibility & Sustainability Reports (BRSR), Principle 6, filed on NSE. Every row comes from the company's machine-readable BRSR XBRL file. The `source_url` column links that file and `pdf_url` links the human-readable BRSR. The filing list came from NSE's corporate-filings API (`/api/corporate-bussiness-sustainabilitiy`, filings from Apr 2024 to Mar 2025).
- **Universe:** the 50 Nifty 50 constituents on NSE's current list (`data/raw/nifty50.csv`, Oct 2026). Eternal and TMPV filed as ZOMATO and TATAMOTORS.
- **Coverage:** **49 of 50 companies.** Each has FY2023-24 and FY2022-23, because the FY24 BRSR also reports the prior year. That gives 98 company-years.
  - **Gap:** Mahindra & Mahindra. Both its XBRL and PDF links on NSE return 404, so it is excluded.
  - JIO Financial listed in Aug 2023. Its FY2022-23 values are all zero, so that year is dropped.
- **Fields:** Scope 1 and Scope 2 (tCO2e), total and renewable energy (GJ), and revenue from operations (Rs crore, taken from the same filing).
- **Boundary:** 33 filings are standalone and 16 are consolidated, as each company reports it. Revenue always comes from the same filing, so emissions and revenue share a boundary.
- **No numbers were estimated.** Each value is either the filed value, or the filed value converted to the unit that the company's own BRSR PDF states. The data-quality section lists every conversion.

### Data quality: a finding in its own right
**19 of the 49 machine-readable filings (39%) had at least one value that can't be used as tagged:**
- **9 companies** tagged values in the wrong unit, and the PDF shows the correct one. All are logged in `data/corrections.csv` with the PDF link:
  - Emissions filed in million tonnes under a tCO2e tag: NTPC and Tata Steel. Taken as tagged, NTPC's 352 Mt would read as 352 t.
  - Emissions in kilo-tonnes and energy in TJ: ITC.
  - Energy in TJ, MJ or PJ under a GJ tag: NTPC, UltraTech, Adani Ports, TCS, Bajaj Auto and BSE.
  - Axis Bank's XBRL energy value doesn't match its own PDF.
- **8 companies** typed revenue in Rs crore (HCL in Rs million) under a tag meant for rupees. These values are used in crore, flagged in `revenue_note`, and the raw value is kept in `revenue_filed_value`.
- **4 companies** had year-on-year breaks above 3x that are methodology or boundary changes, not real changes. They are excluded from YoY statistics only:
  - Apollo Hospitals' Scope 1 went from 8,033 t to 731,919 t.
  - Tata Consumer: Scope 1 rose about 10x.
  - SBI Life: Scope 1+2 rose 3.6x.
  - Axis Bank: its FY23 revenue was mis-keyed at a tenth of the real figure.
- **Not verified:** Hindalco's BRSR PDF refers readers to its annual report for GHG data. Coal India (2.0 tCO2e per GJ, from fugitive mine methane) and Cipla (0.66) have high emissions-to-energy ratios. All three are kept as filed.

## Method
`extract.py` parses the XBRL, applies `data/corrections.csv`, and writes `data/brsr_emissions.csv`. `audit_units.py` scans the PDFs for the units they state. `analysis.py` computes the metrics, the model, the comparison and the charts.

1. **Intensity** = (Scope 1 + Scope 2) / revenue, in tCO2e per Rs crore.
2. **Scope mix:** Scope 1 as a share of Scope 1+2.
3. **YoY:** FY24 vs FY23 change in absolute emissions and in intensity. Pairs with a break above 3x are excluded.
4. **Sector-relative z-score** of log10 intensity, within each Nifty industry. It is only computed for industries with 3 or more companies, because a z-score inside a 1-2 company "sector" means nothing.
5. **Rohan's (m)y model.** From the deck: put the parameters on a 1-10 scale, plot inputs and transitions on a shared x-axis followed by demands, fit a linear regression, and grade by slope *m* and intercept *y*. An upward line is acceptable, a flat line is neutral, and a negative slope with a positive intercept is brown exposure. The deck has no data, so each mapping below is my assumption:

   | x | Deck factor | BRSR field used | Scaling to 1-10 |
   |---|---|---|---|
   | 1 | Input | total energy consumed (GJ) | min-max on log10 across the 49 companies |
   | 2 | Input | non-renewable share of energy | min-max (linear, already 0-1) |
   | 3 | Transition (brown) | Scope 1 tCO2e (direct fuel and process) | min-max on log10 |
   | 4 | Transition (brown) | Scope 2 tCO2e (purchased power) | min-max on log10 |
   | 5 | Demand | revenue from operations (Rs cr) | min-max on log10 |

   - **x-axis order:** follows the deck: inputs, then transitions, then demands. Demands are placed last because the deck says they "have a larger definition value".
   - **Why log scaling:** emissions span 5 orders of magnitude. On a linear scale almost every company would score 1.
   - **Grade bands (mine; the deck gives no numbers):** *m* > 0.25 is Acceptable, |*m*| ≤ 0.25 is Neutral, and *m* < -0.25 with *y* > 0 is Brown exposure. On a 1-10 scale a negative slope always comes with a positive intercept, so the intercept condition never binds.
   - **Normalisation is cohort-relative:** min-max across these 49 companies, so a company's grade depends on who else is in the set.
6. **Comparison:** Spearman correlation of *m* with intensity, rank gaps, and grade-vs-intensity-tercile disagreements.
7. **Sensitivity:** linear and percentile-rank scaling, grade bands of 0.10 and 0.50, and dropping one parameter.

## Key findings (FY2023-24)
1. **Intensity spans 144,820x.** It runs from Eternal at 0.013 tCO2e/Rs cr to NTPC at 1,946. The median company is at 5.2. **Sector alone explains 74% of the variance in log intensity**, so "who is dirty" is mostly "which industry".
2. **Emissions are extremely concentrated.** The 49 companies emit 675 Mt of Scope 1+2. **Five of them emit 85.8%:** NTPC, UltraTech, Tata Steel, JSW Steel and Reliance. The 12 financial-services firms together emit 0.28%.
3. **The headline improvement mostly comes from revenue growth, not emissions cuts.** Across the 44 clean year-on-year pairs, the median intensity fell 9.3% and intensity fell for 34 companies. Over the same period the median absolute emissions *rose* 2.5% (over the 45 pairs without an emissions break; on the same 44 pairs it is +2.8%).
4. **Within-sector outliers** (z-score of log intensity):
   - Dirtier than peers: BSE (+2.2 vs financials; its purchased power is large relative to its revenue), Coal India (+1.15), Apollo Hospitals (+1.15) and Eicher (+1.08).
   - Cleaner than peers: Adani Enterprises (-1.49), HUL (-1.48, almost entirely renewable power) and Bajaj Auto (-1.34).
5. **The (m)y grade only partly agrees with intensity:** Spearman ρ = -0.55 (n = 49, p < 0.001). It grades 8 companies Acceptable, 29 Neutral and 12 Brown exposure. Where it disagrees, the model is the one that's wrong:
   - Coal India ranks 43rd of 49 on intensity but **9th best** by slope, graded Neutral. Its large revenue (the "demand" point) offsets its large Scope 1.
   - Reliance (41st) is Neutral, and so is Tata Steel (447 tCO2e/Rs cr).
   - Jio Financial and Eternal are 2 of the 3 cleanest companies on intensity, but both get **Brown exposure**. They are small, and their thin energy use is mostly grid power, so the 100% non-renewable-share point drags the slope down.
6. **The grade is fragile:**
   - Switching log to linear min-max scaling changes **32 of 49 grades** (39 become Brown) and drops ρ with intensity to -0.07.
   - Narrowing the Neutral band from 0.25 to 0.10 changes 19 grades.
   - Dropping the energy parameter changes 26.

## Where the model breaks
- **Scale sensitivity.** The grade depends on the normalisation choice (finding 6) and on who else is in the cohort, because min-max is relative. The deck says "(m)y is fixed and independent of scope", but on real data it isn't.
- **Size cancels out.** Revenue (demand) and absolute emissions (transitions) both grow with company size. A slope across them partly measures size, not carbon efficiency. That is why Coal India and Reliance look neutral and small firms look brown. A ratio (intensity) avoids this by construction.
- **Missing Scope 3.** BRSR makes Scope 3 optional, and this dataset covers only Scope 1 and Scope 2. Banks and insurers look clean: 0.74 tCO2e/Rs cr median, 0.28% of emissions. But their real exposure is financed emissions (Scope 3, category 15), which isn't in the data. The same goes for automakers' use-phase emissions and Coal India's and ONGC's sold-product combustion.
- **Sector mix.** With 74% of the variance between sectors, a cross-sector grade mostly ranks industries. Only the sector z-score compares like with like, and 8 of the 15 Nifty industries have fewer than 3 companies.
- **Unit errors in the source.** 39% of filings needed a correction or exclusion. Taken at face value, the XBRL would have made NTPC and Tata Steel look like the cleanest companies in India.

## SQL layer
The core metrics are re-derived in SQL on DuckDB, straight from `data/brsr_emissions.csv` and `data/corrections.csv`, as an independent check on the pandas code. `run_sql.py` runs each file, saves the result to `sql/results/<name>.csv`, and asserts it matches `data/company_metrics.csv` and the numbers in this README.

| File | Question | SQL used |
|---|---|---|
| `sql/01_intensity.sql` | FY24 intensity per company | CTE |
| `sql/02_sector_rank.sql` | Rank within sector, sector median | `RANK()`, `PERCENT_RANK()`, `MEDIAN() OVER (PARTITION BY sector)` |
| `sql/03_yoy.sql` | YoY change in emissions and intensity, >3x breaks excluded | `LAG() OVER (PARTITION BY symbol ORDER BY fy)`, chained CTEs |
| `sql/04_concentration.sql` | Cumulative share of emissions (top 5 = 85.8%, NTPC 52.2%) | `SUM() OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` |
| `sql/05_sector_zscore.sql` | z-score of log10 intensity, sectors with 3+ companies | `AVG()`/`STDDEV_SAMP() OVER (PARTITION BY sector)` |
| `sql/06_data_quality.sql` | Companies with unit corrections, by error type | `CASE`, `GROUP BY ROLLUP`, `STRING_AGG` |

All asserts pass. One wording issue it caught: the +2.5% median emissions change is over 45 pairs (Axis Bank's break is in revenue only), not the 44 used for intensity; on those 44 it is +2.8%. Finding 3 now says so.

## Files
| Path | What |
|---|---|
| `data/brsr_emissions.csv` | Raw panel: 49 companies x 2 FYs, with source URLs |
| `data/corrections.csv` | Every unit correction, with the filed value, the corrected value, the reason and a PDF link |
| `data/pdf_unit_audit.csv` | Units each BRSR PDF states for Scope 1 and energy |
| `data/company_metrics.csv` | FY24 metrics, z-scores and (m)y fit per company |
| `data/my_model_sensitivity.csv` | Grade counts and rank stability under 7 model variants |
| `data/analysis_output.txt` | Full printed output of the last run |
| `charts/1_intensity_by_sector.png` | Intensity by sector (log scale) |
| `charts/2_sector_relative_outliers.png` | Sector z-scores |
| `charts/3_my_slope_vs_intensity.png` | (m)y slope vs intensity, coloured by grade |
| `charts/4_my_model_examples.png` | The (m)y fit for three real companies |
| `sql/*.sql`, `run_sql.py` | SQL re-derivation of the metrics (DuckDB) and its asserts |
| `sql/results/` | One CSV per SQL file |
| `data/raw/` | Downloaded XBRL, BRSR PDF text, the NSE filing index and the Nifty 50 list |

## Reproduce
```bash
python3 -m venv .venv && .venv/bin/pip install pandas matplotlib scipy
.venv/bin/python extract.py        # XBRL -> data/brsr_emissions.csv (applies data/corrections.csv)
.venv/bin/python audit_units.py    # optional: PDF unit audit
.venv/bin/python analysis.py       # metrics, model, charts
.venv/bin/pip install duckdb && .venv/bin/python run_sql.py   # SQL layer -> sql/results/, asserts it matches the Python
```
To re-download the raw files, use the URLs in `data/raw/fy24_filings.json`. NSE's archive host accepts a plain browser User-Agent. The API needs a cookie from `www.nseindia.com` first.

## Credit
Extends the (m)y model concept by Rohan Choudhary (IIT Patna), used with permission. The original concept deck is `../references/carbon-footprint-model-rohan.pdf`. The data pipeline, metrics, model implementation, tests and findings are new work.

## Reproducing
Raw NSE XBRL files and BRSR PDFs (~240 MB) are not committed. `analysis.py` and `run_sql.py` run directly on the committed `data/brsr_emissions.csv` and `data/corrections.csv`; every number in the report is in `data/analysis_output.txt`. Re-extracting from source needs the XBRL/PDF downloads in `data/raw/`.
