-- Q3: Week 2 Hold events; repeated holds count as separate events here.
-- ROW_NUMBER chooses exactly two reasons, ties broken by reason text ascending.
-- result: q3_hold_reasons
WITH reasons AS (
    SELECT o.hub_id, l.hold_reason, COUNT(*) AS holds,
           CASE WHEN l.hold_reason IN ('Late Dispatch','Not Attempted','Agent Time Shortage')
                THEN COUNT(*) ELSE 0 END AS agent_side_holds
    FROM order_logs l JOIN orders o ON o.order_id = l.order_id
    WHERE l.status = 'Hold' AND l.event_time >= '2026-10-20' AND l.event_time < '2026-10-27'
    GROUP BY o.hub_id, l.hold_reason
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY hub_id ORDER BY holds DESC, hold_reason ASC) AS ranking
    FROM reasons
)
SELECT h.hub_id, h.hub_name, COALESCE(SUM(r.holds), 0) AS total_holds,
       COALESCE(SUM(r.agent_side_holds), 0) AS agent_side_holds,
       1.0 * SUM(r.agent_side_holds) / NULLIF(SUM(r.holds), 0) AS agent_side_share,
       MAX(CASE WHEN ranking = 1 THEN hold_reason END) AS top_reason_1,
       MAX(CASE WHEN ranking = 1 THEN holds END) AS top_reason_1_count,
       MAX(CASE WHEN ranking = 2 THEN hold_reason END) AS top_reason_2,
       MAX(CASE WHEN ranking = 2 THEN holds END) AS top_reason_2_count
FROM hubs h LEFT JOIN ranked r ON r.hub_id = h.hub_id
GROUP BY h.hub_id, h.hub_name ORDER BY h.hub_id;
