-- Business question: how carbon-intensive is each Nifty 50 company in FY2023-24,
-- measured as Scope 1+2 emissions per Rs crore of revenue (tCO2e / Rs cr)?
WITH fy24 AS (
    SELECT symbol, company, sector, revenue_cr,
           scope1_tco2e, scope2_tco2e,
           scope1_tco2e + scope2_tco2e AS total_tco2e
    FROM read_csv_auto('data/brsr_emissions.csv')
    WHERE fy = 'FY2023-24'
)
SELECT symbol, company, sector, revenue_cr, total_tco2e,
       total_tco2e / revenue_cr   AS intensity,
       scope1_tco2e / total_tco2e AS scope1_share
FROM fy24
ORDER BY intensity;
