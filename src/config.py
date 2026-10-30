"""Source contracts and reporting boundaries; no calculated results live here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "processed" / "carrybee.sqlite3"
OUTPUTS = ROOT / "outputs"
START = "2026-10-13"
WEEK2 = "2026-10-20"
END = "2026-10-26"
AGENT_HOLDS = {"Late Dispatch", "Not Attempted", "Agent Time Shortage"}
CUSTOMER_HOLDS = {"Customer Unreachable", "Customer Rescheduled", "Address Incomplete"}
FILE_IDS = {
    "hubs": "1nMXHUYxfNfOu7Evpcw1I05G8KtWzfozd",
    "agents": "1G3gVf87OD1UY7pMBSl9jkpXRXbnJiLaH",
    "orders": "1dXDPB_C5iYB75ghr3POorOw8jWKpHWjH",
    "order_logs": "1OjRD49U9aF_2WnN5LO-iptAFYg8sGOch",
    "agent_salary": "1mszp5gdvWmk04wh-VQri-krBOot99n1u",
    "costs": "1OLCIykkUxkzsZUOKC5Y6aFaKHv0-eqzc",
    "rules": "1fDg113qN_IlMPzNhoPY9AzF8KBz_jD1Y",
    "volume_forecast": "1Im-j7UJa5YbcqoB9_iUed-dooipSSNUp",
}
HEADERS = {
    "hubs": ["hub_id", "hub_name", "cluster"],
    "agents": ["agent_id", "agent_name", "hub_id", "salary_type", "joining_date", "active_status"],
    "orders": ["order_id", "hub_id", "created_at", "final_status", "cod_amount", "delivery_charge"],
    "order_logs": ["log_id", "order_id", "agent_id", "status", "hold_reason", "event_time", "attempt_no"],
    "agent_salary": ["salary_type", "monthly_salary", "daily_allowance", "allowance_per_delivery"],
    "costs": ["what", "amount_bdt", "when_charged"],
    "rules": ["rule", "value"],
    "volume_forecast": ["hub_id", "week_start", "week_end", "expected_orders"],
}
