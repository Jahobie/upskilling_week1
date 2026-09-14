-- Q4: Median load_ms per plan.
WITH joined AS (
    SELECT u.plan, p.load_ms
    FROM pageviews p
    JOIN users u ON u.user_id = p.user_id
)
SELECT plan, ROUND(MEDIAN(load_ms), 1) AS median_load_ms
FROM joined
GROUP BY plan
ORDER BY plan;
