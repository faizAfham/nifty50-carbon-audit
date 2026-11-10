-- Business question: how concentrated are Nifty 50 Scope 1+2 emissions in FY2023-24?
-- Cumulative share of the total, largest emitter first (top 5 = 85.8%, NTPC alone ~52%).
WITH fy24 AS (
    SELECT symbol, sector, scope1_tco2e + scope2_tco2e AS total_tco2e
    FROM read_csv_auto('data/brsr_emissions.csv')
    WHERE fy = 'FY2023-24'
)
SELECT ROW_NUMBER() OVER (ORDER BY total_tco2e DESC) AS emitter_rank,
       symbol, sector, total_tco2e,
       total_tco2e / SUM(total_tco2e) OVER () AS share,
       SUM(total_tco2e) OVER (ORDER BY total_tco2e DESC ROWS UNBOUNDED PRECEDING)
           / SUM(total_tco2e) OVER ()          AS cumulative_share
FROM fy24
ORDER BY emitter_rank;
