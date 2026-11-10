-- Business question: which companies are dirtier or cleaner than their own sector peers?
-- z-score of log10(FY2023-24 intensity) within sector; only sectors with 3+ companies.
WITH fy24 AS (
    SELECT symbol, sector,
           (scope1_tco2e + scope2_tco2e) / revenue_cr AS intensity
    FROM read_csv_auto('data/brsr_emissions.csv')
    WHERE fy = 'FY2023-24'
),
stats AS (
    SELECT *, LOG10(intensity) AS log_int,
           COUNT(*)                     OVER s AS sector_n,
           AVG(LOG10(intensity))        OVER s AS sector_mean_log,
           STDDEV_SAMP(LOG10(intensity)) OVER s AS sector_sd_log
    FROM fy24
    WINDOW s AS (PARTITION BY sector)
)
SELECT symbol, sector, intensity, sector_n,
       (log_int - sector_mean_log) / sector_sd_log AS sector_z
FROM stats
WHERE sector_n >= 3
ORDER BY sector_z;
