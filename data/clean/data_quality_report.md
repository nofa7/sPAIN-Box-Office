# Data quality report

- Raw rows: weekly_top25=8525, weekly_spanish=10304, annual_spanish=4832
- Garbled PDF rows fixed by hand (overlapping text): 19
- Duplicate film-weekend rows dropped: 0
- Duplicate film-weekend rows dropped: 0
- top25: suspicious admissions values=51, imputed from cumulative=28, estimated from weekend median ticket price=23
- spanish: suspicious admissions values=1, imputed from cumulative=0, estimated from weekend median ticket price=1
- Top25 rows with missing screens (left null): 603
- Distinct original-title keys: 2281; film releases after title linking: 2250
- Top25 films flagged Spanish via weekly list: 553; via annual-list fallback: 7
- Clean rows: fact_weekend_top25=8525, fact_weekend_spanish=10304, fact_annual_spanish=4832, dim_film=2250, dim_distributor=318
- Negative weekend gross: 0
- Rows where cumulative gross < weekend gross: 0
- Duplicate (weekend, rank) pairs in Top 25: 0
- Implied ticket price (gross/admissions) range: 3.13 - 24.53 EUR (median 6.96)
- Films whose first Top-25 appearance is not week 1 (opened outside Top 25): 97
- Re-releases flagged: 92
