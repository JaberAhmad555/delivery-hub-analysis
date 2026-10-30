"""Build a small deployable snapshot of validated aggregates; no raw orders/names."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import pandas as pd

from src.config import ROOT, OUTPUTS
from src.scenario_analysis import load_model, STRATEGIC, HUB_IDS

SNAPSHOT = ROOT / "dashboard_data"


def prepare_snapshot(destination: Path = SNAPSHOT) -> dict:
    model = load_model()
    frames, results = model.inputs["frames"], model.inputs["results"]
    destination.mkdir(parents=True, exist_ok=True)
    hubs = frames["hubs"].copy()
    daily = results["q1_agent_day"]
    daily_hub = daily.groupby(["day", "week", "hub_id", "hub_name"], as_index=False).agg(
        attempts=("attempts", "sum"), delivered=("delivered", "sum"), holds=("holds", "sum"), returned=("returned", "sum"),
        agent_days=("agent_id", "size"))
    orders = frames["orders"].copy()
    orders["week"] = orders.created_at.str[:10].map(lambda d: 1 if d < "2026-10-20" else 2)
    orders["delivered_final"] = orders.final_status.eq("Delivered").astype(int)
    orders["returned_final"] = orders.final_status.eq("Returned").astype(int)
    orders["hold_final"] = orders.final_status.eq("Hold").astype(int)
    cohort = orders.groupby(["hub_id", "week"], as_index=False).agg(
        orders=("order_id", "size"), delivered_final=("delivered_final", "sum"), returned_final=("returned_final", "sum"), hold_final=("hold_final", "sum"))
    historical = results["q2_utilisation"].merge(cohort, on=["hub_id", "week"], validate="one_to_one")
    historical = historical.merge(results["q6_delivery_costs"].drop(columns=["hub_name"]), on=["hub_id", "week"], validate="one_to_one")
    events = daily_hub.groupby(["hub_id", "week"], as_index=False)[["delivered", "holds", "returned"]].sum()
    historical = historical.merge(events, on=["hub_id", "week"], validate="one_to_one").merge(hubs[["hub_id", "cluster"]], on="hub_id")
    logs = frames["order_logs"].merge(frames["orders"][["order_id", "hub_id"]], on="order_id", validate="many_to_one")
    logs["week"] = logs.event_time.str[:10].map(lambda d: 1 if d < "2026-10-20" else 2)
    reasons = logs[logs.status.eq("Hold")].groupby(["hub_id", "week", "hold_reason"]).size().reset_index(name="hold_events")
    reasons["agent_side"] = reasons.hold_reason.isin(["Late Dispatch", "Not Attempted", "Agent Time Shortage"])
    aliases = {agent: f"Agent {i+1:02d}" for i, agent in enumerate(sorted(frames["agents"].agent_id))}
    productivity = daily.groupby(["hub_id", "agent_id", "week"], as_index=False).agg(
        eligible_days=("day", "size"), attempts=("attempts", "sum"), delivered=("delivered", "sum"),
        holds=("holds", "sum"), returned=("returned", "sum"))
    productivity["agent"] = productivity.agent_id.map(aliases)
    productivity["deliveries_per_day"] = productivity.delivered / productivity.eligible_days
    productivity["return_ratio"] = productivity.returned / productivity.attempts.replace(0, float("nan"))
    productivity = productivity.drop(columns=["agent_id"])
    high = results["q5_high_return_agents"].copy()
    high["agent"] = high.agent_id.map(aliases)
    high = high[["hub_id", "hub_name", "agent", "attempts", "returned_attempts", "return_ratio"]]
    exports = {"hubs": hubs, "historical_hub_week": historical, "daily_hub": daily_hub, "hold_reasons": reasons,
               "agent_productivity": productivity, "high_return_agents": high, "held_orders": results["q4_held_orders"],
               "forecast": results["q7_staffing_forecast"]}
    for name in ["scenario_comparison", "weekly_staffing_plan", "budget_allocation", "risk_register", "sensitivity_analysis"]:
        exports[name] = pd.read_csv(STRATEGIC / f"{name}.csv")
    # The local risk register contains operational IDs for HR follow-up; public
    # dashboard text refers to anonymised labels instead.
    exports["risk_register"] = exports["risk_register"].replace(
        {"A1045": aliases["A1045"], "A1046": aliases["A1046"], "A1047": aliases["A1047"]}, regex=True)
    manifest = json.loads((STRATEGIC / "scenario_manifest.json").read_text(encoding="utf-8"))
    files = {}
    forbidden = {"order_id", "log_id", "agent_name", "joining_date", "event_time", "created_at", "cod_amount", "agent_id"}
    for name, frame in exports.items():
        if forbidden.intersection(frame.columns):
            raise ValueError(f"Private source columns in {name}")
        path = destination / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        files[path.name] = {"rows": len(frame), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    meta = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "historical_period": "13-26 October 2026",
            "forecast_period": "27 October-23 November 2026", "recommended": manifest["recommended"],
            "phase1_validated": True, "phase1_unchanged": manifest["phase1_unchanged"],
            "privacy": "Hub aggregates and anonymised agent summaries only. No raw order/log records, real agent names or raw IDs.",
            "files": files}
    (destination / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (destination / "README.md").write_text(
        "# Dashboard snapshot\n\nGenerated by `python -m src.prepare_dashboard_data` from validated Phase 1 results and "
        "Phase 2 scenarios. These approved display aggregates support a clean cloud startup without raw datasets or network downloads. "
        "Agent labels are pseudonyms; underlying operational metrics remain employer-supplied assessment data. "
        "No raw order IDs, event records, agent names or salary records are included. "
        "Hashes in metadata.json verify snapshot completeness at app startup. Refresh locally after analysis changes, review and commit.\n",
        encoding="utf-8")
    return {"files": len(files), "rows": sum(x["rows"] for x in files.values()), "destination": str(destination)}


if __name__ == "__main__":
    print(json.dumps(prepare_snapshot(), indent=2))
