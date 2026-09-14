-- Filter orders by fiscal year 2025 q3 jul 1 - sep 30 2025 and status = 'completed'
-- Get total order amounts 
-- Get refunds in q3 2025 and subtract from order amounts
-- find max category order_if with highest amount from order amounts - refund amounts in Q3 2025
WITH q3_sales AS (
SELECT
    o.order_id,
    p.category,
    o.quantity * p.unit_price AS gross_amount
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.order_date >= '2025-07-01'
    AND o.order_date <'2025-10-01'
    AND o.status = 'completed'
),

refund_totals AS (
    SELECT order_id, SUM(amount) AS refund_amount
    FROM refunds
    GROUP BY order_id
),

q3_net AS (
    SELECT
        q.category,
        q.gross_amount - COALESCE(r.refund_amount, 0) AS net_amount
    FROM q3_sales q
    LEFT JOIN refund_totals r ON q.order_id = r.order_id
),

category_revenue AS (
    SELECT category, SUM(net_amount) AS net_revenue
    FROM q3_net
    GROUP BY category

)

SELECT category, net_revenue
FROM category_revenue
ORDER BY net_revenue DESC
LIMIT 1;





