-- Eight source tables. Dates/timestamps are validated ISO text before import.
PRAGMA foreign_keys = ON;
CREATE TABLE hubs (
    hub_id TEXT PRIMARY KEY, hub_name TEXT NOT NULL UNIQUE, cluster TEXT NOT NULL
) STRICT;
CREATE TABLE agent_salary (
    salary_type TEXT PRIMARY KEY CHECK(salary_type IN ('Fixed','Variable')),
    monthly_salary REAL NOT NULL CHECK(monthly_salary >= 0),
    daily_allowance REAL NOT NULL CHECK(daily_allowance >= 0),
    allowance_per_delivery REAL NOT NULL CHECK(allowance_per_delivery >= 0)
) STRICT;
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY, agent_name TEXT NOT NULL,
    hub_id TEXT NOT NULL REFERENCES hubs(hub_id),
    salary_type TEXT NOT NULL REFERENCES agent_salary(salary_type),
    joining_date TEXT NOT NULL, active_status TEXT NOT NULL CHECK(active_status IN ('Active','Inactive'))
) STRICT;
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY, hub_id TEXT NOT NULL REFERENCES hubs(hub_id),
    created_at TEXT NOT NULL, final_status TEXT NOT NULL CHECK(final_status IN ('Delivered','Hold','Returned')),
    cod_amount REAL NOT NULL CHECK(cod_amount >= 0), delivery_charge REAL NOT NULL CHECK(delivery_charge >= 0)
) STRICT;
CREATE TABLE order_logs (
    log_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    status TEXT NOT NULL CHECK(status IN ('Assigned','Delivered','Hold','Returned')),
    hold_reason TEXT,
    event_time TEXT NOT NULL, attempt_no INTEGER NOT NULL CHECK(attempt_no BETWEEN 1 AND 3),
    CHECK((status = 'Hold' AND hold_reason IS NOT NULL AND length(hold_reason) > 0)
       OR (status != 'Hold' AND hold_reason IS NULL))
) STRICT;
CREATE UNIQUE INDEX one_assignment_per_attempt ON order_logs(order_id, attempt_no) WHERE status = 'Assigned';
CREATE UNIQUE INDEX one_outcome_per_attempt ON order_logs(order_id, attempt_no) WHERE status != 'Assigned';
CREATE INDEX logs_agent_time ON order_logs(agent_id, event_time);
CREATE INDEX logs_status_time ON order_logs(status, event_time);
CREATE INDEX orders_hub_created ON orders(hub_id, created_at);
CREATE TABLE costs (
    what TEXT PRIMARY KEY, amount_bdt REAL NOT NULL CHECK(amount_bdt >= 0), when_charged TEXT NOT NULL
) STRICT;
CREATE TABLE rules (rule TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
CREATE TABLE volume_forecast (
    hub_id TEXT NOT NULL REFERENCES hubs(hub_id), week_start TEXT NOT NULL, week_end TEXT NOT NULL,
    expected_orders INTEGER NOT NULL CHECK(expected_orders >= 0),
    PRIMARY KEY(hub_id, week_start), CHECK(julianday(week_end) - julianday(week_start) = 6)
) STRICT;
