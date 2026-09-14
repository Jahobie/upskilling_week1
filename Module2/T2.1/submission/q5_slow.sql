-- SLOW starter for Q5 (users whose first-ever pageview was '/pricing').
-- Correct but uses a correlated NOT EXISTS self-join over 120k pageviews.
-- Your job: rewrite with a window function (ROW_NUMBER) to return the SAME
-- count far faster.
WITH firsts AS (
    SELECT
        p.url_path,
        (SELECT COUNT(*) FROM pageviews p2
         WHERE p2.user_id = p.user_id
           AND (p2.ts < p.ts OR (p2.ts = p.ts AND p2.view_id < p.view_id))
        ) AS earlier_views
    FROM pageviews p
)
SELECT COUNT(*) AS users_first_touch_pricing
FROM firsts
WHERE earlier_views = 0 AND url_path = '/pricing';


