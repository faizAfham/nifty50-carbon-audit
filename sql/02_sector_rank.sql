-- Business question: where does each company sit within its own sector on FY2023-24
-- intensity (1 = cleanest), and what is the sector's median intensity?
WITH fy24 AS (
    SELECT symbol, sector,
           (scope1_tco2e + scope2_tco2e) / revenue_cr AS intensity
    FROM read_csv_auto('data/brsr_emissions.csv')
    WHERE fy = 'FY2023-24'
)
SELECT symbol, sector, intensity,
       RANK()         OVER w                        AS sector_rank,
       PERCENT_RANK() OVER w                        AS sector_pct_rank,
       COUNT(*)       OVER (PARTITION BY sector)    AS sector_n,
       MEDIAN(intensity) OVER (PARTITION BY sector) AS sector_median_intensity
FROM fy24
WINDOW w AS (PARTITION BY sector ORDER BY intensity)
ORDER BY sector_median_intensity, sector_rank;
