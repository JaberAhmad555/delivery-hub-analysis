-- Q7 BASELINE PROJECTION: no hires, transfers or hold programme assumed.
-- Historical multiplier = W2 Assigned events / W2 newly created orders in each hub.
-- This period flow measure includes carry-in retries and assumes stable retry/backlog mix.
-- It avoids treating orders as attempts; end-of-period censored retries remain a limitation.
-- Required agents = CEILING(forecast_orders * multiplier / (7 * 40 * 0.85)).
-- Full-precision arithmetic is retained through the final ceiling; displayed rounding is not reused.
-- A missing/zero historical denominator yields NULL, never a fabricated multiplier.
-- result: q7_staffing_forecast
WITH attempts AS (
    SELECT o.hub_id, COUNT(*) AS historical_attempts
    FROM order_logs l JOIN orders o ON o.order_id = l.order_id
    WHERE l.status = 'Assigned' AND l.event_time >= '2026-10-20' AND l.event_time < '2026-10-27'
    GROUP BY o.hub_id
), arrivals AS (
    SELECT hub_id, COUNT(*) AS historical_new_orders FROM orders
    WHERE created_at >= '2026-10-20' AND created_at < '2026-10-27' GROUP BY hub_id
), workforce AS (
    SELECT hub_id, COUNT(*) AS current_active_agents FROM agents
    WHERE active_status = 'Active' AND joining_date <= '2026-10-26' GROUP BY hub_id
), parameters AS (
    SELECT CAST((SELECT value FROM rules WHERE rule = 'Standard attempts per agent per day') AS REAL)
         * CAST((SELECT value FROM rules WHERE rule = 'Target utilisation') AS REAL) AS target_attempts_per_agent_day
), forecast AS (
    SELECT h.hub_id, h.hub_name, h.cluster, f.week_start, f.week_end,
           f.expected_orders AS forecast_orders, a.historical_attempts, n.historical_new_orders,
           1.0 * a.historical_attempts / NULLIF(n.historical_new_orders, 0) AS attempts_per_order,
           1.0 * f.expected_orders * a.historical_attempts / NULLIF(n.historical_new_orders, 0) AS expected_attempts,
           COALESCE(w.current_active_agents, 0) AS current_active_agents,
           p.target_attempts_per_agent_day,
           CAST(julianday(f.week_end) - julianday(f.week_start) + 1 AS INTEGER) AS operating_days,
           'Projected baseline' AS metric_type
    FROM volume_forecast f JOIN hubs h ON h.hub_id = f.hub_id
    LEFT JOIN attempts a ON a.hub_id = f.hub_id LEFT JOIN arrivals n ON n.hub_id = f.hub_id
    LEFT JOIN workforce w ON w.hub_id = f.hub_id CROSS JOIN parameters p
), raw_need AS (
    SELECT *, expected_attempts / NULLIF(operating_days * target_attempts_per_agent_day, 0) AS unrounded_agents
    FROM forecast
), rounded AS (
    SELECT *, CAST(unrounded_agents AS INTEGER) + (unrounded_agents > CAST(unrounded_agents AS INTEGER)) AS required_agents
    FROM raw_need
)
SELECT *, required_agents - current_active_agents AS staffing_gap,
       CASE WHEN required_agents IS NULL THEN NULL ELSE MAX(required_agents - current_active_agents, 0) END AS shortage,
       CASE WHEN required_agents IS NULL THEN NULL ELSE MAX(current_active_agents - required_agents, 0) END AS surplus
FROM rounded ORDER BY hub_id, week_start;
