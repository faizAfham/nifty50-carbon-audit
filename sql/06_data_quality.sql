-- Business question: how many companies' machine-readable (XBRL) filings needed a unit or value
-- correction, and of which kind? Source: data/corrections.csv (each fix verified against the BRSR PDF).
WITH c AS (
    SELECT symbol, field, reason,
           CASE
               WHEN reason ILIKE '%does not match%'              THEN 'value does not match PDF'
               WHEN field LIKE 'scope%' AND reason ILIKE '%million%' THEN 'emissions in million tonnes'
               WHEN field LIKE 'scope%' AND reason ILIKE '%kilo%'    THEN 'emissions in kilo-tonnes'
               WHEN field LIKE 'energy%'                          THEN 'energy in MJ/TJ under GJ tag'
               ELSE 'other'
           END AS error_type
    FROM read_csv_auto('data/corrections.csv')
)
SELECT COALESCE(error_type, 'ANY (total)') AS error_type,
       COUNT(DISTINCT symbol) AS companies,
       COUNT(*)               AS corrected_values,
       STRING_AGG(DISTINCT symbol, ', ' ORDER BY symbol) AS symbols
FROM c
GROUP BY ROLLUP (error_type)
ORDER BY error_type NULLS LAST;
