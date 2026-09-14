WITH firsts AS (
    SELECT 
        p.user_id, p.url_path, p.ts, p.view_id,
        row_number() OVER (PARTITION BY user_id ORDER BY ts, view_id) as earlier_views
    FROM pageviews p
)

SELECT COUNT(*) AS users_first_touch_pricing
FROM firsts
WHERE earlier_views = 1 AND url_path = '/pricing';