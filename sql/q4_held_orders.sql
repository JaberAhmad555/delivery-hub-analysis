-- Q4: DISTINCT order cohort with >=1 Hold event during the historical period.
-- final_status is the source snapshot at October 26, validated against latest outcome.
-- Denominator is distinct ever-held orders, not hold events or attempts.
-- result: q4_held_orders
WITH held AS (
    SELECT DISTINCT order_id FROM order_logs
    WHERE status = 'Hold' AND event_time >= '2026-10-13' AND event_time < '2026-10-27'
), cohort AS (
    SELECT o.* FROM orders o JOIN held x ON x.order_id = o.order_id
)
SELECT h.hub_id, h.hub_name, COUNT(c.order_id) AS ever_held_orders,
       COALESCE(SUM(c.final_status = 'Delivered'), 0) AS delivered_orders,
       COALESCE(SUM(c.final_status = 'Returned'), 0) AS returned_orders,
       COALESCE(SUM(c.final_status = 'Hold'), 0) AS still_held_orders,
       1.0 * SUM(c.final_status = 'Delivered') / NULLIF(COUNT(c.order_id), 0) AS delivered_share,
       1.0 * SUM(c.final_status = 'Returned') / NULLIF(COUNT(c.order_id), 0) AS returned_share,
       1.0 * SUM(c.final_status = 'Hold') / NULLIF(COUNT(c.order_id), 0) AS still_held_share
FROM hubs h LEFT JOIN cohort c ON c.hub_id = h.hub_id
GROUP BY h.hub_id, h.hub_name ORDER BY h.hub_id;
