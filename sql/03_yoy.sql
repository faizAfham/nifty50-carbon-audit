-- Business question: did emissions and emissions intensity fall from FY2022-23 to FY2023-24?
-- A >3x jump either way in emissions or revenue is a boundary/methodology/unit break, not real change,
-- so it is excluded (same rule as analysis.py). Emissions YoY excludes only emissions breaks;
-- intensity YoY excludes emissions or revenue breaks. JIO Financial's FY2022-23 (pre-listing, all zero) is dropped.
WITH panel AS (
    SELECT symbol, fy, scope1_tco2e + scope2_tco2e AS total_tco2e, revenue_cr
    FROM read_csv_auto('data/brsr_emissions.csv')
    WHERE NOT (symbol = 'JIOFIN' AND fy = 'FY2022-23')
),
lagged AS (
    SELECT *,
           LAG(total_tco2e) OVER w AS prev_tco2e,
           LAG(revenue_cr)  OVER w AS prev_revenue_cr
    FROM panel
    WINDOW w AS (PARTITION BY symbol ORDER BY fy)
),
flagged AS (
    SELECT symbol,
           total_tco2e / prev_tco2e   AS emis_ratio,
           revenue_cr / prev_revenue_cr AS rev_ratio,
           (total_tco2e / prev_tco2e   NOT BETWEEN 1/3 AND 3) AS emis_break,
           (revenue_cr / prev_revenue_cr NOT BETWEEN 1/3 AND 3) AS rev_break
    FROM lagged
    WHERE fy = 'FY2023-24' AND prev_tco2e IS NOT NULL
),
yoy AS (
    SELECT symbol, emis_break OR rev_break AS yoy_break,
           CASE WHEN NOT emis_break THEN emis_ratio - 1 END                          AS emissions_yoy,
           CASE WHEN NOT (emis_break OR rev_break) THEN emis_ratio / rev_ratio - 1 END AS intensity_yoy,
           CASE WHEN NOT (emis_break OR rev_break) THEN emis_ratio - 1 END           AS emissions_yoy_same_pairs
    FROM flagged
)
SELECT *,
       COUNT(emissions_yoy)            OVER () AS n_emissions_pairs,
       MEDIAN(emissions_yoy)           OVER () AS median_emissions_yoy,
       COUNT(intensity_yoy)            OVER () AS n_intensity_pairs,
       MEDIAN(intensity_yoy)           OVER () AS median_intensity_yoy,
       MEDIAN(emissions_yoy_same_pairs) OVER () AS median_emissions_yoy_same_pairs,
       COUNT(*) FILTER (WHERE intensity_yoy < 0) OVER () AS n_intensity_fell
FROM yoy
ORDER BY intensity_yoy NULLS LAST;
