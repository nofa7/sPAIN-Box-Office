-- Spain Box Office case study - Analyze step (DuckDB SQL)
-- Run with: py scripts/04_analysis.py   (loads data/clean/*.csv as views, runs each query,
-- writes results to analysis/<name>.csv). Each query starts with a "-- name:" line.
-- Scope: Top 25 weekend charts, Jan 2020 - Nov 2026. 2020-21 are COVID years (closures,
-- capacity limits); "post-COVID" = 2022 onward. 2026 is year-to-date (to 15 Nov).

-- name: q01_market_by_year
-- Top 25 weekend gross and admissions per year, with Spanish share.
SELECT year(w.weekend_start)                                    AS year,
       count(DISTINCT w.weekend_start)                          AS weekends,
       round(sum(w.gross_eur) / 1e6, 1)                         AS gross_m_eur,
       round(sum(w.admissions) / 1e6, 2)                        AS admissions_m,
       round(sum(w.gross_eur) / count(DISTINCT w.weekend_start) / 1e6, 2) AS avg_weekend_gross_m_eur,
       round(sum(w.gross_eur) / sum(w.admissions), 2)           AS avg_ticket_eur,
       round(100 * sum(CASE WHEN f.origin = 'Spanish' THEN w.gross_eur END) / sum(w.gross_eur), 1)
                                                                AS spanish_share_pct
FROM fact_weekend_top25 w JOIN dim_film f USING (film_id)
GROUP BY 1 ORDER BY 1;

-- name: q02_seasonality_month
-- Average Top 25 weekend gross by calendar month, post-COVID (2022+).
SELECT month(weekend_start)                                     AS month_num,
       strftime(min(weekend_start), '%b')                       AS month,
       count(DISTINCT weekend_start)                            AS weekends,
       round(sum(gross_eur) / count(DISTINCT weekend_start) / 1e6, 2) AS avg_weekend_gross_m_eur
FROM fact_weekend_top25
WHERE weekend_start >= DATE '2022-01-01'
GROUP BY 1 ORDER BY 1;

-- name: q03_release_month_performance
-- New releases (opened in Top 25, no re-releases), post-COVID: how films perform by release month.
SELECT release_month_num,
       count(*)                                                 AS films,
       round(median(opening_gross_eur) / 1e3, 0)                AS median_opening_k_eur,
       round(median(total_gross_eur) / 1e3, 0)                  AS median_total_k_eur,
       round(median(legs_multiple), 2)                          AS median_legs,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND release_year BETWEEN 2022 AND 2026
GROUP BY 1 ORDER BY 1;

-- name: q04_origin_comparison
-- Spanish vs foreign new releases, post-COVID.
SELECT origin,
       count(*)                                                 AS films,
       round(sum(total_gross_eur) / 1e6, 1)                     AS total_gross_m_eur,
       round(median(opening_gross_eur) / 1e3, 0)                AS median_opening_k_eur,
       round(median(total_gross_eur) / 1e3, 0)                  AS median_total_k_eur,
       round(median(legs_multiple), 2)                          AS median_legs,
       round(median(opening_per_screen_eur), 0)                 AS median_opening_per_screen_eur,
       round(median(weeks_in_top25), 1)                         AS median_weeks_in_top25,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND release_year BETWEEN 2022 AND 2026
GROUP BY 1;

-- name: q05_distributor_type_share
-- Majors vs independents: share of Top 25 gross per year.
SELECT year(w.weekend_start)                                     AS year,
       d.distributor_type,
       round(sum(w.gross_eur) / 1e6, 1)                          AS gross_m_eur,
       round(100 * sum(w.gross_eur) / sum(sum(w.gross_eur)) OVER (PARTITION BY year(w.weekend_start)), 1)
                                                                 AS share_pct
FROM fact_weekend_top25 w
JOIN dim_film f USING (film_id)
JOIN dim_distributor d ON d.distributor = f.distributor
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q06_distributor_league
-- Distributor league table, post-COVID new releases: volume, gross, hit rate, efficiency.
SELECT f.distributor,
       d.distributor_type,
       count(*)                                                  AS films,
       sum(CASE WHEN f.origin = 'Spanish' THEN 1 ELSE 0 END)     AS spanish_films,
       round(sum(f.total_gross_eur) / 1e6, 1)                    AS total_gross_m_eur,
       round(median(f.total_gross_eur) / 1e3, 0)                 AS median_gross_k_eur,
       round(avg(CASE WHEN f.total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS hit_rate_1m_pct,
       round(median(f.legs_multiple), 2)                         AS median_legs
FROM dim_film f JOIN dim_distributor d USING (distributor)
WHERE f.opened_in_top25 AND NOT f.is_rerelease AND f.release_year BETWEEN 2022 AND 2026
GROUP BY 1, 2 HAVING count(*) >= 5
ORDER BY total_gross_m_eur DESC;

-- name: q07_concentration
-- How concentrated is the box office? Share of yearly Top 25 gross captured by the top 10 films.
WITH film_year AS (
    SELECT year(weekend_start) AS year, film_id, sum(gross_eur) AS gross
    FROM fact_weekend_top25 GROUP BY 1, 2
), ranked AS (
    SELECT *, row_number() OVER (PARTITION BY year ORDER BY gross DESC) AS rn,
              count(*) OVER (PARTITION BY year) AS films
    FROM film_year
)
SELECT year, max(films) AS films_in_top25,
       round(100 * sum(CASE WHEN rn <= 10 THEN gross END) / sum(gross), 1) AS top10_share_pct,
       round(100 * sum(CASE WHEN rn <= ceil(films * 0.2) THEN gross END) / sum(gross), 1) AS top20pct_films_share_pct
FROM ranked GROUP BY 1 ORDER BY 1;

-- name: q08_width_vs_gross
-- Release width: opening cinemas band vs outcomes (post-COVID new releases).
-- Cinemas, not screens: the source stopped reporting screens in June 2026.
SELECT CASE WHEN opening_cinemas < 50  THEN '1) <50'
            WHEN opening_cinemas < 150 THEN '2) 50-149'
            WHEN opening_cinemas < 250 THEN '3) 150-249'
            WHEN opening_cinemas < 325 THEN '4) 250-324'
            ELSE '5) 325+' END                                   AS opening_cinemas_band,
       count(*)                                                  AS films,
       round(median(opening_gross_eur) / 1e3, 0)                 AS median_opening_k_eur,
       round(median(total_gross_eur) / 1e3, 0)                   AS median_total_k_eur,
       round(median(opening_gross_eur / opening_cinemas), 0)     AS median_opening_per_cinema_eur,
       round(median(legs_multiple), 2)                           AS median_legs,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND opening_cinemas IS NOT NULL
  AND release_year BETWEEN 2022 AND 2026
GROUP BY 1 ORDER BY 1;

-- name: q09_weekly_decay
-- Average week-over-week change in weekend gross, by week on release and origin (post-COVID).
SELECT w.weeks_on_release AS week,
       f.origin,
       count(*)                                                  AS observations,
       round(median(w.gross_pct_change), 1)                      AS median_wow_change_pct
FROM fact_weekend_top25 w JOIN dim_film f USING (film_id)
WHERE w.weeks_on_release BETWEEN 2 AND 8 AND w.gross_pct_change IS NOT NULL
  AND w.weekend_start >= DATE '2022-01-01' AND NOT f.is_rerelease
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q10_season_release
-- Release season (incl. Christmas/Easter windows) vs outcomes, split by origin (post-COVID).
SELECT release_season, origin,
       count(*)                                                  AS films,
       round(median(total_gross_eur) / 1e3, 0)                   AS median_total_k_eur,
       round(median(legs_multiple), 2)                           AS median_legs,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND release_year BETWEEN 2022 AND 2026
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q11_competition
-- Crowded weekends: number of new Top-25 entries on a weekend vs median opening of those entries.
WITH openers AS (
    SELECT weekend_start, count(*) AS new_entries, median(gross_eur) AS med_open
    FROM fact_weekend_top25 WHERE weeks_on_release = 1 AND weekend_start >= DATE '2022-01-01'
    GROUP BY 1
)
SELECT new_entries, count(*) AS weekends, round(median(med_open) / 1e3, 0) AS median_opening_k_eur
FROM openers GROUP BY 1 ORDER BY 1;

-- name: q12_spanish_annual
-- Spanish cinema 2016-2026 (all Spanish films, ICAA annual lists): totals and dependence on hits.
WITH r AS (
    SELECT *, row_number() OVER (PARTITION BY year ORDER BY gross_eur DESC) AS rn
    FROM fact_annual_spanish
)
SELECT year, count(*) AS films_on_release,
       round(sum(gross_eur) / 1e6, 1) AS gross_m_eur,
       round(sum(admissions) / 1e6, 2) AS admissions_m,
       round(100 * sum(CASE WHEN rn <= 5 THEN gross_eur END) / sum(gross_eur), 1) AS top5_share_pct,
       sum(CASE WHEN gross_eur >= 1e6 THEN 1 ELSE 0 END) AS films_over_1m,
       bool_or(is_partial_year) AS partial_year
FROM r GROUP BY 1 ORDER BY 1;

-- name: q13_top_films
-- Top 15 films by total gross in the window.
SELECT title, distributor, origin, release_weekend, opening_screens,
       round(opening_gross_eur / 1e6, 2) AS opening_m_eur,
       round(total_gross_eur / 1e6, 2) AS total_m_eur, legs_multiple
FROM dim_film ORDER BY total_gross_eur DESC LIMIT 15;

-- name: q14_top_spanish_films
-- Top 15 Spanish films by total gross in the window.
SELECT title, distributor, release_weekend, opening_screens,
       round(opening_gross_eur / 1e6, 2) AS opening_m_eur,
       round(total_gross_eur / 1e6, 2) AS total_m_eur, legs_multiple
FROM dim_film WHERE origin = 'Spanish' ORDER BY total_gross_eur DESC LIMIT 15;

-- ============ Question 3 (continued): Spanish vs foreign releases in depth ============

-- name: q15_origin_by_year
-- Spanish vs foreign new releases per release year: volume, share of releases vs share of gross.
SELECT release_year, origin,
       count(*)                                                  AS new_releases,
       round(100 * count(*) / sum(count(*)) OVER (PARTITION BY release_year), 1) AS share_of_releases_pct,
       round(sum(total_gross_eur) / 1e6, 1)                      AS release_gross_m_eur,
       round(100 * sum(total_gross_eur) / sum(sum(total_gross_eur)) OVER (PARTITION BY release_year), 1)
                                                                 AS share_of_gross_pct,
       round(median(opening_gross_eur) / 1e3, 0)                 AS median_opening_k_eur,
       round(median(total_gross_eur) / 1e3, 0)                   AS median_total_k_eur,
       round(median(opening_cinemas), 0)                         AS median_opening_cinemas,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND release_year BETWEEN 2020 AND 2026
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q16_origin_by_width
-- Same opening width, different origin: does a Spanish film perform differently at equal width?
SELECT opening_cinemas_band, origin,
       count(*)                                                  AS films,
       round(median(total_gross_eur) / 1e3, 0)                   AS median_total_k_eur,
       round(median(opening_gross_eur / opening_cinemas), 0)     AS median_opening_per_cinema_eur,
       round(median(legs_multiple), 2)                           AS median_legs,
       round(avg(CASE WHEN total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film
WHERE opened_in_top25 AND NOT is_rerelease AND opening_cinemas_band IS NOT NULL
  AND release_year BETWEEN 2022 AND 2026
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: q17_origin_by_distributor_type
-- Who releases Spanish films? Majors vs independents, post-COVID new releases.
SELECT f.origin, d.distributor_type,
       count(*)                                                  AS films,
       round(sum(f.total_gross_eur) / 1e6, 1)                    AS release_gross_m_eur,
       round(100 * sum(f.total_gross_eur) / sum(sum(f.total_gross_eur)) OVER (PARTITION BY f.origin), 1)
                                                                 AS share_of_origin_gross_pct,
       round(median(f.total_gross_eur) / 1e3, 0)                 AS median_total_k_eur,
       round(median(f.opening_cinemas), 0)                       AS median_opening_cinemas,
       round(avg(CASE WHEN f.total_gross_eur >= 1e6 THEN 1 ELSE 0 END) * 100, 1) AS pct_over_1m
FROM dim_film f JOIN dim_distributor d USING (distributor)
WHERE f.opened_in_top25 AND NOT f.is_rerelease AND f.release_year BETWEEN 2022 AND 2026
GROUP BY 1, 2 ORDER BY 1, 2;
