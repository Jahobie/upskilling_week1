-- Q1: For each country, the single most-viewed url_path (ties -> path A→Z).
WITH counts AS (
    SELECT country, url_path, COUNT(*) AS views
    FROM pageviews
    GROUP BY country, url_path
),
ranked AS (
    SELECT country, url_path, views,
           ROW_NUMBER() OVER (PARTITION BY country ORDER BY views DESC, url_path ASC) AS rn
    FROM counts
)
SELECT country, url_path, views
FROM ranked
WHERE rn = 1
ORDER BY country;
