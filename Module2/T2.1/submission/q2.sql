-- Q2: 7-day moving average of daily total pageviews, for March 2025 only.
-- Daily totals are computed over the full dataset first so the trailing
-- 7-day window for early March days can see late-February activity.
-- A calendar spine fills in any day with zero pageviews so the ROWS-based
-- window always means 7 calendar days, not just 7 rows present in the data.
WITH calendar AS (
    SELECT unnest(generate_series(
        (SELECT MIN(CAST(ts AS DATE)) FROM pageviews),
        (SELECT MAX(CAST(ts AS DATE)) FROM pageviews),
        INTERVAL 1 DAY
    ))::DATE AS day
),
daily AS (
    SELECT c.day, COALESCE(COUNT(p.view_id), 0) AS views
    FROM calendar c
    LEFT JOIN pageviews p ON CAST(p.ts AS DATE) = c.day
    GROUP BY c.day
),
with_avg AS (
    SELECT day, views,
           AVG(views) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS mov_avg_7d
    FROM daily
)
SELECT day, views, ROUND(mov_avg_7d, 2) AS mov_avg_7d
FROM with_avg
WHERE day BETWEEN DATE '2025-03-01' AND DATE '2025-03-31'
ORDER BY day;
