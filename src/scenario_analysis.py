"""Q8-Q10: deterministic, auditable intervention scenarios using Phase 1 outputs.

The optimiser minimises accumulated hub-level queues under a strict 85% planning
cap. Those queues are distinct from queues at the standard 40-attempt workload.
No overtime, speculative revenue or cash value of freed capacity is booked.
"""
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from datetime import date, timedelta
import hashlib
import json
import math

import numpy as np
import pandas as pd

from src.config import ROOT, OUTPUTS, RAW
from src.load_data import read_sources
from src.validation import validate_sources, validate_results
from src.export_results import markdown_table

BUDGET = 70000
HUB_IDS = ("H01", "H02", "H03", "H04", "H05", "H06")
STRATEGIC = OUTPUTS / "strategic"


@dataclass(frozen=True)
class Plan:
    name: str
    hires: tuple[int, ...] = (0, 0, 0, 0, 0, 0)
    transfers: tuple[tuple[str, str, int], ...] = ()
    programmes: tuple[str, ...] = ()
    salary_type: str = "Fixed"


@dataclass(frozen=True)
class Assumptions:
    payroll_days: int = 28
    ramp: str = "delayed"
    programme_effectiveness: float = 1.0
    programme_delay: int = 14
    demand_factor: float = 1.0
    first_week_productivity: float = 0.6
    transferred_first_week_productivity: float = 1.0


@dataclass
class Model:
    hubs: pd.DataFrame
    forecast: pd.DataFrame
    utilisation: pd.DataFrame
    holds: pd.DataFrame
    daily_orders: np.ndarray
    attempts_per_order: np.ndarray
    agent_holds_per_order: np.ndarray
    all_holds_per_order: np.ndarray
    returns_per_order: np.ndarray
    delivery_yield: np.ndarray
    workforce: np.ndarray
    mean_delivery_charge: np.ndarray
    transfer_options: tuple
    inputs: dict


def phase1_hashes() -> dict:
    paths = list((ROOT / "sql").glob("*.sql")) + list(OUTPUTS.glob("q*.csv"))
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def load_model() -> Model:
    frames = read_sources()
    validate_sources(frames)
    names = ["q1_agent_day", "q1_hub_summary", "q2_utilisation", "q3_hold_reasons", "q4_held_orders",
             "q5_high_return_agents", "q6_delivery_costs", "q7_staffing_forecast"]
    results = {name: pd.read_csv(OUTPUTS / f"{name}.csv") for name in names}
    validate_results(frames, results)
    hubs = frames["hubs"].set_index("hub_id").loc[list(HUB_IDS)].reset_index()
    forecast = results["q7_staffing_forecast"].sort_values(["hub_id", "week_start"])
    w2 = results["q2_utilisation"].query("week == 2").set_index("hub_id").loc[list(HUB_IDS)]
    h = results["q3_hold_reasons"].set_index("hub_id").loc[list(HUB_IDS)]
    first = forecast.drop_duplicates("hub_id").set_index("hub_id").loc[list(HUB_IDS)]
    orders = forecast.forecast_orders.to_numpy().reshape(6, 4)
    daily_orders = np.repeat(orders / 7, 7, axis=1)
    new_orders = first.historical_new_orders.to_numpy(dtype=float)
    logs = frames["order_logs"].merge(frames["orders"][["order_id", "hub_id"]], on="order_id", validate="many_to_one")
    event_counts = pd.crosstab(logs.loc[logs.event_time.ge("2026-10-20"), "hub_id"], logs.loc[logs.event_time.ge("2026-10-20"), "status"]).reindex(HUB_IDS)
    charges = frames["orders"].query("final_status == 'Delivered'").groupby("hub_id").delivery_charge.mean().reindex(HUB_IDS).to_numpy()
    options = []
    # Do not create donor overload: maximum transfer is its minimum four-week
    # surplus at target, in addition to the mandatory pre-transfer <75% rule.
    peak_need = forecast.groupby("hub_id").required_agents.max()
    clusters = hubs.set_index("hub_id").cluster.to_dict()
    workforce = first.current_active_agents.to_numpy(dtype=int)
    for i, donor in enumerate(HUB_IDS):
        if w2.loc[donor, "utilisation"] >= 0.75:
            continue
        maximum = max(0, int(workforce[i] - peak_need[donor]))
        for recipient in HUB_IDS:
            if recipient != donor and clusters[donor] == clusters[recipient] and maximum:
                options.append((donor, recipient, maximum))
    return Model(hubs, forecast, w2, h, daily_orders,
                 first.attempts_per_order.to_numpy(), h.agent_side_holds.to_numpy() / new_orders,
                 h.total_holds.to_numpy() / new_orders, event_counts.Returned.to_numpy() / new_orders,
                 event_counts.Delivered.to_numpy() / event_counts.Assigned.to_numpy(), workforce,
                 charges, tuple(options), {"frames": frames, "results": results})


def validate_plan(model: Model, plan: Plan) -> None:
    if len(plan.hires) != 6 or any(type(n) is not int or n < 0 for n in plan.hires):
        raise ValueError("Hires must be six non-negative integers")
    if plan.salary_type not in {"Fixed", "Variable"}:
        raise ValueError("Unknown salary type")
    if len(set(plan.programmes)) != len(plan.programmes) or not set(plan.programmes) <= set(HUB_IDS):
        raise ValueError("Invalid or duplicate programme hub")
    clusters = model.hubs.set_index("hub_id").cluster.to_dict()
    outgoing = {hub: 0 for hub in HUB_IDS}
    seen = set()
    for source, target, number in plan.transfers:
        if source not in HUB_IDS or target not in HUB_IDS or source == target:
            raise ValueError("Invalid transfer endpoints")
        if (source, target) in seen or type(number) is not int or number <= 0:
            raise ValueError("Duplicate transfer or invalid transfer count")
        seen.add((source, target))
        if clusters[source] != clusters[target]:
            raise ValueError("Transfers must remain within the same cluster")
        if model.utilisation.loc[source, "utilisation"] >= 0.75:
            raise ValueError("Donor Week 2 utilisation must be strictly below 75%")
        outgoing[source] += number
    for i, hub in enumerate(HUB_IDS):
        if outgoing[hub] > model.workforce[i]:
            raise ValueError("Cannot transfer more existing agents than available")


def programme_ramp(assumptions: Assumptions) -> np.ndarray:
    if assumptions.ramp not in {"delayed", "linear"} or assumptions.programme_delay < 0:
        raise ValueError("Invalid hold programme ramp")
    if not 0 <= assumptions.programme_effectiveness <= 1:
        raise ValueError("Programme effectiveness must be between zero and one")
    day = np.arange(28)
    if assumptions.ramp == "delayed":
        ramp = (day >= assumptions.programme_delay).astype(float)
    else:
        ramp = np.minimum(day / max(assumptions.programme_delay, 1), 1)
    return 0.5 * assumptions.programme_effectiveness * ramp


def queue_path(demand: np.ndarray, capacity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Independent queues per hub, carried daily; no pooling across clusters."""
    backlog = np.zeros_like(demand)
    served = np.zeros_like(demand)
    current = np.zeros(demand.shape[0])
    for day in range(demand.shape[1]):
        available = current + demand[:, day]
        served[:, day] = np.minimum(available, capacity[:, day])
        current = np.maximum(available - served[:, day], 0)
        backlog[:, day] = current
    return backlog, served


def evaluate(model: Model, plan: Plan, assumptions: Assumptions = Assumptions(), detailed: bool = True) -> tuple[dict, pd.DataFrame]:
    validate_plan(model, plan)
    if assumptions.payroll_days not in {26, 28} or assumptions.demand_factor <= 0:
        raise ValueError("Payroll days must be 26 or 28; demand must be positive")
    if not 0 <= assumptions.first_week_productivity <= 1 or not 0 <= assumptions.transferred_first_week_productivity <= 1:
        raise ValueError("Productivity must be between zero and one")
    hire = np.array(plan.hires)
    delta = np.zeros(6)
    arrivals = np.zeros(6)
    for source, target, count in plan.transfers:
        delta[HUB_IDS.index(source)] -= count
        delta[HUB_IDS.index(target)] += count
        arrivals[HUB_IDS.index(target)] += count
    old_workforce = model.workforce + delta
    productivity = np.ones(28)
    productivity[:7] = assumptions.first_week_productivity
    effective = old_workforce[:, None] + hire[:, None] * productivity
    effective[:, :7] -= arrivals[:, None] * (1 - assumptions.transferred_first_week_productivity)
    target_capacity = effective * 34
    standard_capacity = effective * 40
    new_orders = model.daily_orders * assumptions.demand_factor
    baseline_attempts = new_orders * model.attempts_per_order[:, None]
    mask = np.array([hub in plan.programmes for hub in HUB_IDS], dtype=float)
    avoided_holds = new_orders * model.agent_holds_per_order[:, None] * mask[:, None] * programme_ramp(assumptions)
    # Each avoided Hold removes one next-day retry. No cascade multiplier.
    # The final day's avoided retry belongs outside the 28-day horizon.
    avoided_retries = np.zeros_like(avoided_holds)
    avoided_retries[:, 1:] = avoided_holds[:, :-1]
    demand = np.maximum(baseline_attempts - avoided_retries, 0)
    target_backlog, target_served = queue_path(demand, target_capacity)
    hard_backlog, hard_served = queue_path(demand, standard_capacity)
    one_time = int(hire.sum()) * 5000 + sum(t[2] for t in plan.transfers) * 2000 + len(plan.programmes) * 15000
    hire_delivery_estimate = (hard_served * model.delivery_yield[:, None] * np.divide(
        hire[:, None] * productivity, effective, out=np.zeros_like(effective), where=effective != 0)).sum(axis=1)
    fixed_salary = float(hire.sum() * 650 * assumptions.payroll_days) if plan.salary_type == "Fixed" else 0.0
    daily_allowance = float(hire.sum() * 300 * assumptions.payroll_days) if plan.salary_type == "Variable" else 0.0
    delivery_allowance = float(hire_delivery_estimate.sum() * 14) if plan.salary_type == "Variable" else 0.0
    # Variable payroll reservation covers every effective standard-workload
    # attempt being delivered. Fixed pay gives the budget certainty used in search.
    allowance_ceiling = float(hire.sum() * (21 + 7 * assumptions.first_week_productivity) * 40 * 14) if plan.salary_type == "Variable" else 0.0
    payroll = fixed_salary + daily_allowance + delivery_allowance
    payroll_reserve = fixed_salary + daily_allowance + allowance_ceiling
    gross_savings = float(avoided_holds.sum() * 30)
    budget_used = one_time + payroll_reserve
    total_cash = one_time + payroll
    direct_net = gross_savings - total_cash
    summary = {
        "scenario": plan.name, "salary_type": plan.salary_type, "payroll_days": assumptions.payroll_days,
        "ramp": assumptions.ramp, "demand_factor": assumptions.demand_factor,
        "hires": int(hire.sum()), "transfers": sum(t[2] for t in plan.transfers), "programmes": len(plan.programmes),
        "one_time_cost_bdt": one_time, "new_fixed_salary_bdt": fixed_salary,
        "new_daily_allowance_bdt": daily_allowance, "new_delivery_allowance_estimate_bdt": delivery_allowance,
        "new_payroll_estimate_bdt": payroll, "new_payroll_reserve_bdt": payroll_reserve,
        "budget_reserved_bdt": budget_used, "remaining_budget_bdt": BUDGET - budget_used,
        "budget_feasible": budget_used <= BUDGET, "avoided_hold_events": float(avoided_holds.sum()),
        "avoided_reattempts_in_horizon": float(avoided_retries.sum()), "avoided_retries_after_horizon": float(avoided_holds[:, -1].sum()),
        "direct_hold_cost_savings_bdt": gross_savings,
        "incremental_operating_cost_bdt": payroll - gross_savings,
        "total_incremental_cash_cost_bdt": total_cash - gross_savings,
        "recognised_incremental_revenue_bdt": 0.0, "net_direct_cash_benefit_bdt": direct_net,
        "direct_cash_roi": direct_net / total_cash if total_cash else np.nan,
        "planning_backlog_attempt_days": float(target_backlog.sum()),
        "end_planning_backlog": float(target_backlog[:, -1].sum()),
        "peak_hub_planning_backlog": float(target_backlog.max()),
        "hard_backlog_attempt_days": float(hard_backlog.sum()), "end_hard_backlog": float(hard_backlog[:, -1].sum()),
        "required_attempts": float(demand.sum()), "served_attempts_at_standard": float(hard_served.sum()),
        "plan": json.dumps({"hires": dict(zip(HUB_IDS, plan.hires)), "transfers": plan.transfers, "programmes": plan.programmes}),
    }
    if not detailed:
        return summary, pd.DataFrame()
    rows = []
    for i, hub in enumerate(HUB_IDS):
        for w in range(4):
            sl = slice(w * 7, (w + 1) * 7)
            base_capacity = model.workforce[i] * 7 * 34
            capacity = float(target_capacity[i, sl].sum())
            standard = float(standard_capacity[i, sl].sum())
            fresh = float(demand[i, sl].sum())
            baseline = float(baseline_attempts[i, sl].sum())
            rows.append({"scenario": plan.name, "hub_id": hub, "hub_name": model.hubs.iloc[i].hub_name,
                         "cluster": model.hubs.iloc[i].cluster, "forecast_week": w + 1,
                         "week_start": (date(2026, 10, 27) + timedelta(days=7*w)).isoformat(),
                         "forecast_orders": float(new_orders[i, sl].sum()), "baseline_attempts": baseline,
                         "required_attempts_after_programme": fresh, "existing_agents": int(model.workforce[i]),
                         "net_transfers": int(delta[i]), "new_hires": int(hire[i]),
                         "roster_agents": int(old_workforce[i] + hire[i]), "effective_agent_days": float(effective[i, sl].sum()),
                         "baseline_target_capacity": base_capacity, "target_capacity": capacity, "standard_capacity": standard,
                         "baseline_utilisation": baseline / (model.workforce[i] * 7 * 40),
                         "projected_utilisation": fresh / standard if standard else np.nan,
                         "baseline_target_gap": max(baseline - base_capacity, 0), "target_gap": max(fresh - capacity, 0),
                         "planning_backlog_week_end": float(target_backlog[i, (w + 1)*7 - 1]),
                         "hard_backlog_week_end": float(hard_backlog[i, (w + 1)*7 - 1]),
                         "hard_backlog_attempt_days": float(hard_backlog[i, sl].sum()),
                         "avoided_holds": float(avoided_holds[i, sl].sum()), "avoided_reattempts": float(avoided_retries[i, sl].sum()),
                         "hold_cost_savings_bdt": float(avoided_holds[i, sl].sum() * 30),
                         "projected_remaining_holds": float((new_orders[i, sl] * model.all_holds_per_order[i] - avoided_holds[i, sl]).sum()),
                         "projected_returns_unchanged": float(new_orders[i, sl].sum() * model.returns_per_order[i]),
                         "programme": hub in plan.programmes, "metric_type": "Projected; daily volume assumed uniform within week"})
    return summary, pd.DataFrame(rows)


def hire_vectors(total_max: int, size: int = 6):
    if size == 1:
        for n in range(total_max + 1):
            yield (n,)
    else:
        for n in range(total_max + 1):
            for tail in hire_vectors(total_max - n, size - 1):
                yield (n,) + tail


def optimise(model: Model, assumptions: Assumptions = Assumptions()) -> tuple[Plan, dict]:
    """Exhaustive fixed-pay search over all hubs and safe transfer counts.

    Evaluate all feasible nonnegative integer hire allocations (0..3 total),
    every programme subset and each donor-preserving same-cluster transfer.
    No cross-hub capacity pooling or hardcoded recommendation.
    """
    maximum_hires = BUDGET // (5000 + 650 * assumptions.payroll_days)
    best, best_key, best_score, count = None, None, None, 0
    transfer_ranges = [range(option[2] + 1) for option in model.transfer_options]
    for hires in hire_vectors(maximum_hires):
        for counts in product(*transfer_ranges):
            transfers = tuple((source, target, n) for (source, target, _), n in zip(model.transfer_options, counts) if n)
            base_cost = sum(hires) * (5000 + 650 * assumptions.payroll_days) + sum(counts) * 2000
            for programme_mask in product([0, 1], repeat=6):
                if base_cost + sum(programme_mask) * 15000 > BUDGET:
                    continue
                programme = tuple(h for h, selected in zip(HUB_IDS, programme_mask) if selected)
                plan = Plan("Optimised", hires, transfers, programme)
                score, _ = evaluate(model, plan, assumptions, detailed=False)
                count += 1
                key = (round(score["planning_backlog_attempt_days"], 6), round(score["end_planning_backlog"], 6),
                       score["budget_reserved_bdt"], hires, transfers, programme)
                if best_key is None or key < best_key:
                    best, best_key, best_score = plan, key, score
    return best, {"feasible_plans_evaluated": count, "objective": "Minimise sum of hub/day planning backlog at 85%; then ending backlog; then reserved cost",
                  "search_scope": "Fixed salary; all six hub hire allocations; all programme subsets; transfers preserving donors' peak forecast capacity",
                  "best": best_score}


def allocate_hires_greedily(model: Model, count: int) -> tuple[int, ...]:
    """Allocate an eight-hire proposal by marginal service benefit, not arbitrary split."""
    hires = [0] * 6
    for _ in range(count):
        candidates = []
        for hub in range(6):
            candidate = hires.copy()
            candidate[hub] += 1
            score, _ = evaluate(model, Plan("Hire allocation", tuple(candidate)), detailed=False)
            candidates.append((score["planning_backlog_attempt_days"], hub))
        _, choice = min(candidates)
        hires[choice] += 1
    return tuple(hires)


def budget_rows(model: Model, plan: Plan, payroll_days: int = 28) -> pd.DataFrame:
    rows = []
    names = model.hubs.set_index("hub_id").hub_name.to_dict()
    for source, target, n in plan.transfers:
        rows.append({"item": f"Transfer {names[source]} to {names[target]}", "hub_id": target, "quantity": n,
                     "unit_cost_bdt": 2000, "amount_bdt": n * 2000, "category": "One-time", "timing": "Day 1"})
    for hub, count in zip(HUB_IDS, plan.hires):
        if count:
            rows.extend([{"item": f"Recruit fixed agents: {names[hub]}", "hub_id": hub, "quantity": count,
                          "unit_cost_bdt": 5000, "amount_bdt": count * 5000, "category": "One-time", "timing": "Day 1"},
                         {"item": f"Fixed pay: {names[hub]} ({payroll_days} days)", "hub_id": hub, "quantity": count,
                          "unit_cost_bdt": 650 * payroll_days, "amount_bdt": count * 650 * payroll_days,
                          "category": "New-agent payroll", "timing": "Days 1-28"}])
    for hub in plan.programmes:
        rows.append({"item": f"Hold programme: {names[hub]}", "hub_id": hub, "quantity": 1,
                     "unit_cost_bdt": 15000, "amount_bdt": 15000, "category": "One-time", "timing": "Day 1; effect after Day 14"})
    spent = sum(row["amount_bdt"] for row in rows)
    rows.append({"item": "Unallocated contingency", "hub_id": "All", "quantity": 1, "unit_cost_bdt": BUDGET - spent,
                 "amount_bdt": BUDGET - spent, "category": "Remaining budget", "timing": "Not spent"})
    return pd.DataFrame(rows)


def risk_register(model: Model, recommended: Plan) -> pd.DataFrame:
    riverside = float(model.holds.loc["H03", "agent_side_share"])
    data = [
        ("Demand above forecast", "Assigned attempts vs daily forecast; projected utilisation", ">10% forecast variance over 3 days OR >95% standard utilisation over 2 days", "Daily; 3-day rolling", "Hub Operations + Planning", "Rebalance routes; use contingency only after refreshed 28-day budget; prioritise ageing orders", "Stress tests +10% and +20%; volume is uniform within each forecast week, not an observed daily pattern"),
        ("New-agent ramp below plan", "Attempts per new-hire paid day relative to comparable experienced agents", "Below 60% in days 1-7; red flag below 40% for 2 days; below 85% by day 10", "Daily, reviews on days 3/7/10/14", "Hub Manager + Training", "Buddy routes, dispatch support and targeted coaching; revisit gap before adding staff", "Base 60% first 7 days, then 100%; stress 40% first week"),
        ("Hold programme underperforms", "Agent-side holds per 100 new orders, adjusted for workload; dispatch adherence", "Day 7: <90% dispatch checklist adherence; day 14: <90% trained staff; days 15-17: <25% reduction vs Week 2 rate", "Daily; formal days 7/14/17", "Riverside Manager + Process Excellence", "Audit Late Dispatch, Not Attempted and Time Shortage; fix route cut-offs; no early savings assumed", f"Week 2 Riverside agent-side share {riverside:.2%}; base has no outcome benefit in first 14 days; stress 50% effectiveness and 21-day delay"),
        ("Capacity shortfall", "Required attempts / effective standard capacity; actual open/aged assigned orders", ">85% for 3 days prompts planning; >100% for any day or >1 day actual oldest overdue triggers escalation", "Daily, morning and evening", "Control Tower + Hub Operations", "Temporarily operate between 85% and 100% with daily review; cap route load at standard and clear actual backlog", "Modelled planning queues at 85% are not observed backlog; standard-capacity queues shown separately"),
        ("Customer holds and returns", "Customer-side Hold/Assigned and Returned/Assigned; agent return ratios", ">20% relative increase vs hub Week 2 for 3 days with >=100 attempts; established agent >15% return ratio over >=30 attempts", "Daily; weekly agent review", "Customer Support + Quality", "Address validation and customer calls; review Brookside A1045/A1046/A1047 locally; investigate before performance action", "Programme does not remove customer-side holds or returns; no return-cost savings booked"),
        ("Transfer disruption", "Donor and recipient utilisation; attendance and transfer-agent productivity", "Donor projected >85% after move, recipient transfer productivity <80% for 2 days, or any missed shift", "Before move; daily for first 7 days", "HR + Cluster A Manager", "Confirm roster and same-cluster route familiarity; phase move if attendance fails; reverse if donor forecast deteriorates", "Only donors strictly below 75% in Week 2; search preserves peak donor target coverage; stress 80% first-week transfer productivity"),
        ("Budget overrun", "Committed one-time spend + 28-day new payroll reserve", ">BDT 70,000 prohibited; warn when uncommitted contingency <BDT 2,000 or any quote >10% above approved unit cost", "Before purchase; twice weekly", "Finance + HR", "Track 28 paid days explicitly; fixed contracts for new hires; no spending of forecast savings until realised", "26-day sensitivity is not authority to pay 28 days with a 26-day reserve"),
    ]
    return pd.DataFrame(data, columns=["risk", "kpi", "threshold", "frequency", "owner", "mitigation", "basis"])


def generate() -> dict:
    before = phase1_hashes()
    model = load_model()
    best28, search28 = optimise(model)
    best26, search26 = optimise(model, Assumptions(payroll_days=26))
    best28 = replace(best28, name="Recommended - robust 28-day budget")
    best26 = replace(best26, name="26-day budget optimum")
    peak = model.forecast.groupby("hub_id").required_agents.max().reindex(HUB_IDS).to_numpy()
    need = tuple(int(max(0, n)) for n in peak - model.workforce)
    eight = allocate_hires_greedily(model, 8)
    safe_transfers = tuple((s, t, min(n, max(0, int(peak[HUB_IDS.index(t)] - model.workforce[HUB_IDS.index(t)])))) for s, t, n in model.transfer_options)
    safe_transfers = tuple(t for t in safe_transfers if t[2] > 0)
    scenarios = [Plan("Baseline - no intervention"), Plan("Eight fixed hires", eight),
                 Plan("Eight variable hires", eight, salary_type="Variable"),
                 Plan("Transfers only", transfers=safe_transfers), Plan("Selective fixed hires", need),
                 Plan("Selective variable hires", need, salary_type="Variable"),
                 Plan("Riverside programme only", programmes=("H03",)),
                 Plan("Transfer + Riverside programme", transfers=safe_transfers, programmes=("H03",)),
                 Plan("Transfer + two Hillcrest hires", (0, 0, 0, 2, 0, 0), safe_transfers),
                 Plan("Transfer + three hub programmes", transfers=safe_transfers, programmes=("H01", "H03", "H04")),
                 best28, replace(best26, name="26-day optimum costed at 28 days")]
    summaries, weeklies = [], []
    for plan in scenarios:
        summary, weekly = evaluate(model, plan)
        summaries.append(summary)
        weeklies.append(weekly)
    sensitivity = []
    cases = {"Base - 28 days, delayed effect": Assumptions(), "26 paid days, same plan": Assumptions(payroll_days=26),
             "Linear hold ramp over 14 days": Assumptions(ramp="linear"), "Half programme effectiveness": Assumptions(programme_effectiveness=0.5),
             "Programme delayed until day 22": Assumptions(programme_delay=21), "Demand +10%": Assumptions(demand_factor=1.1),
             "Demand +20%": Assumptions(demand_factor=1.2), "New-hire first week at 40%": Assumptions(first_week_productivity=0.4),
             "Transfers at 80% for first week": Assumptions(transferred_first_week_productivity=0.8),
             "Combined downside": Assumptions(demand_factor=1.1, first_week_productivity=0.4, programme_effectiveness=0.5,
                                                transferred_first_week_productivity=0.8)}
    for label, assumptions in cases.items():
        row, _ = evaluate(model, best28, assumptions)
        sensitivity.append({"sensitivity": label, **row})
    row26, weekly26 = evaluate(model, best26, Assumptions(payroll_days=26))
    sensitivity.append({"sensitivity": "Re-optimised under 26-day budget", **row26})
    comparison = pd.DataFrame(summaries)
    weekly = pd.concat(weeklies, ignore_index=True)
    STRATEGIC.mkdir(parents=True, exist_ok=True)
    tables = {"scenario_comparison": comparison, "weekly_staffing_plan": weekly,
              "budget_allocation": budget_rows(model, best28), "risk_register": risk_register(model, best28),
              "sensitivity_analysis": pd.DataFrame(sensitivity), "26_day_optimal_weekly_plan": weekly26}
    for name, frame in tables.items():
        frame.to_csv(STRATEGIC / f"{name}.csv", index=False, encoding="utf-8-sig")
    after = phase1_hashes()
    if before != after:
        raise RuntimeError("Phase 1 outputs changed during strategic analysis")
    info = {"recommended": {"name": best28.name, "hires": best28.hires, "transfers": best28.transfers, "programmes": best28.programmes},
            "phase1_sha256": before, "phase1_unchanged": True, "search_28": search28, "search_26": search26,
            "model": "Deterministic daily flow, uniform within forecast weeks; 85% planning queues separate from 100% standard queues",
            "scenario_assumptions": {"payroll_days": 28, "hold_programme": "0 effect days 1-14; 50% of agent holds days 15-28",
                                     "retry_lag_days": 1, "new_agent_productivity": "60% first 7 days, 100% thereafter",
                                     "incremental_revenue_bdt": 0, "fixed_new_agent_pay": 650,
                                     "transfer_options": model.transfer_options}}
    (STRATEGIC / "scenario_manifest.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    write_report(model, best28, comparison, weekly, tables, info)
    return {"recommended": info["recommended"], "summary": comparison.query("scenario == @best28.name").iloc[0].to_dict(),
            "plans_evaluated_28_days": search28["feasible_plans_evaluated"], "phase1_unchanged": True}


def write_report(model, recommended, comparison, weekly, tables, info):
    selected = comparison.query("scenario == @recommended.name").iloc[0]
    selected_weekly = weekly.query("scenario == @recommended.name")
    baseline = weekly.query("scenario == 'Baseline - no intervention'")
    baseline_summary = comparison.query("scenario == 'Baseline - no intervention'").iloc[0]
    names = model.hubs.set_index("hub_id").hub_name.to_dict()
    eight = json.loads(comparison.loc[comparison.scenario.eq("Eight fixed hires"), "plan"].iloc[0])["hires"]
    peak_need = model.forecast.groupby("hub_id").required_agents.max()
    decisions = [{"Hub": names[h], "Current": int(model.workforce[i]),
                  "Peak baseline need": int(peak_need[h]), "Eight-hire allocation": eight[h],
                  "Eight-hire cost BDT": eight[h] * (5000 + 28 * 650),
                  "Recommended hires": recommended.hires[i]} for i, h in enumerate(HUB_IDS)]
    allocation = []
    for hub, hires in zip(HUB_IDS, recommended.hires):
        moves = [f"{n} from {names[s]}" for s, t, n in recommended.transfers if t == hub]
        moves += [f"{n} to {names[t]}" for s, t, n in recommended.transfers if s == hub]
        allocation.append({"Hub": names[hub], "Current": int(model.workforce[HUB_IDS.index(hub)]), "Hires": hires,
                           "Transfers": "; ".join(moves) or "None", "Programme": "Yes" if hub in recommended.programmes else "No"})
    headline = ["# CarryBee Phase 2: strategic analysis (Q8-Q10)",
                "Historical evidence: 13-26 October 2026. Projection: 27 October-23 November 2026. All forecast benefits below are modelled, not observed.",
                "## Recommendation",
                f"Do not approve eight hires. Use the intervention plan below, reserving BDT {selected.budget_reserved_bdt:,.0f} "
                f"on a 28-paid-day basis and retaining BDT {selected.remaining_budget_bdt:,.0f} as unallocated contingency.",
                markdown_table(pd.DataFrame(allocation)), "## Q8 - staffing alternatives",
                "The eight-hire proposal is allocated by sequential marginal reduction in the 85% planning queue. "
                "The employer supplied no hub split. Selective hires cover each hub's maximum four-week baseline requirement. "
                "Both fixed and variable contracts are costed; variable pay has an estimated allowance plus a maximum standard-workload reserve.",
                markdown_table(pd.DataFrame(decisions)),
                "Greenfield's two-agent baseline gap is covered by Lakeview transfers; its three hires in the eight-hire comparison "
                "reflect the first-week learning penalty. Hillcrest needs two experienced-equivalent agents throughout the forecast, "
                "so hire two fixed agents and monitor their initial 60% productivity. Riverside has a two-agent peak baseline gap "
                "but 563 of its 874 Week 2 holds are agent-side; fund its programme and manage residual target pressure. "
                "Lakeview, Brookside and Westwood have no baseline hiring gap. Eight fixed hires cost BDT 185,600, "
                "which exceeds the BDT 70,000 budget by BDT 115,600.",
                markdown_table(comparison[["scenario", "hires", "transfers", "programmes", "budget_reserved_bdt", "budget_feasible",
                                           "planning_backlog_attempt_days", "end_planning_backlog", "direct_hold_cost_savings_bdt"]]),
                f"The fixed-pay search evaluated {info['search_28']['feasible_plans_evaluated']:,} feasible plans across all six hubs, "
                "all programme subsets, all affordable integer hiring allocations and safe transfer quantities. It minimises the sum of "
                "daily hub-level backlog under a strict 85% scheduling cap, then ending backlog, then reserved cost. This is a service "
                "objective, not profit maximisation. It is an exhaustive optimum within the stated fixed-pay, day-1 intervention search space; "
                "it is not a global optimum over staggered hires, contract types, overtime or later programme start dates.",
                "Transfer donors must be strictly below 75% Week 2 utilisation, and transfers remain within a cluster. "
                "Lakeview (56.17%) may supply Greenfield; Brookside (71.49%) may supply Westwood. The search also preserves "
                "donor capacity for its highest forecast week: at most three Lakeview and one Brookside agents. "
                "Riverside and Hillcrest are both ineligible donors. Westwood has no baseline shortage, so moving a Brookside agent there "
                "must earn its cost through the objective rather than being assumed useful.",
                "## Q9 - budget and four-week consequences", markdown_table(tables["budget_allocation"]),
                "Existing-agent salary is a baseline expense outside the incremental BDT 70,000 allocation. Select two experienced "
                "fixed-salary Lakeview agents for transfer, subject to HR route and attendance checks; Lakeview has enough fixed staff. "
                "Their fixed pay is unchanged. Existing variable delivery allowances are held at baseline; no savings from replacing "
                "their work are assumed. New fixed hires receive BDT 650/day including their learning period. Salaries are not reduced to 60%; "
                "only productive capacity is. One-time costs are hiring BDT 5,000, transfer BDT 2,000 and programme BDT 15,000.",
                "### Baseline versus recommended, by hub and week",
                markdown_table(selected_weekly[["hub_name", "forecast_week", "baseline_attempts", "required_attempts_after_programme",
                                                "baseline_target_capacity", "target_capacity", "baseline_utilisation", "projected_utilisation",
                                                "planning_backlog_week_end", "hard_backlog_week_end"]]),
                f"Across 28 days, the 85% planning-queue exposure falls from {baseline_summary.planning_backlog_attempt_days:,.1f} "
                f"to {selected.planning_backlog_attempt_days:,.1f} attempt-days. Ending planning queue changes from "
                f"{baseline_summary.end_planning_backlog:,.1f} to {selected.end_planning_backlog:,.1f} attempts. "
                f"The baseline ends with {baseline_summary.end_hard_backlog:,.1f} attempts queued at the 40-attempt standard; "
                f"the intervention ends with {selected.end_hard_backlog:,.1f}. These are deterministic queue estimates, not observed backlogs. "
                "Manage the first 14 days with daily scheduling between the 85% planning target and 100% standard where necessary, "
                "without claiming that every target breach is a lost delivery.",
                "### Benefit accounting and ROI",
                f"The base case prevents {selected.avoided_hold_events:,.2f} Hold events and {selected.avoided_reattempts_in_horizon:,.2f} "
                f"next-day attempts within the horizon. Another {selected.avoided_retries_after_horizon:,.2f} avoided retries fall on day 29 "
                f"and are excluded from 28-day capacity. Direct Hold charges saved are BDT {selected.direct_hold_cost_savings_bdt:,.2f}. "
                f"Incremental operating cost (new payroll minus hold charges saved) is BDT {selected.incremental_operating_cost_bdt:,.2f}; "
                f"including one-time costs, net cash cost is BDT {selected.total_incremental_cash_cost_bdt:,.2f}. "
                f"Package direct-cash ROI is {selected.direct_cash_roi:.2%} over the first 28 days.",
                "Avoided holds generate a single BDT 30 charge saving each. Their one-day-later retries release capacity but have no "
                "separate cash value: existing staff remain paid. No extra return savings, delivery allowance savings, COD revenue or "
                "incremental delivery-fee revenue is booked. Faster delivery is not an extra order. The data do not establish price "
                "realisation, incremental customer demand or a causal link between spare capacity and additional paid deliveries. "
                "Recognised incremental revenue is therefore BDT 0. No positive whole-package cash payback is claimed; the service "
                "objective and risk reduction justify the staffing spend.",
                "Programme-only payback below extrapolates the final two weeks' direct hold-charge savings after the 14-day "
                "no-benefit period, with unchanged volume and no repeat programme fee. It excludes wages and transfer costs and "
                "must not be presented as whole-plan payback."]
    for hub in recommended.programmes:
        saving = float(selected_weekly.query("hub_id == @hub").hold_cost_savings_bdt.sum())
        payback = 14 + 15000 / (saving / 14) if saving else math.inf
        headline += [f"- {names[hub]} programme: 28-day direct savings BDT {saving:,.2f}; programme-only net ROI "
                     f"{(saving - 15000)/15000:.2%}; extrapolated payback {payback:.1f} days after launch."]
    headline += ["### Salary and ramp sensitivities",
                 "Base: all 28 operating days are paid. The 26-day sensitivity pays one monthly fixed salary per new hire "
                 "while retaining seven-day availability; it needs an explicit employment/roster interpretation and does not "
                 "authorise two unpaid working days. The model shows both the same plan under 26 paid days and a re-optimised "
                 "26-day allocation, plus that allocation re-costed at 28 days in the scenario table.",
                 "Base programme timing: zero reduction on days 1-14 and 50% of agent-side holds from day 15. Linear sensitivity: "
                 "zero on day 1, rising to full reduction on day 15. Downside: half promised effectiveness or full effect only "
                 "from day 22. Hold reduction changes agent-side events only, with one avoided next-day retry per prevented hold; "
                 "no cascading retries or return-conversion benefits are added. Historical event rates per new order remain "
                 "constant apart from that explicit intervention.",
                 markdown_table(tables["sensitivity_analysis"][["sensitivity", "budget_reserved_bdt", "budget_feasible", "remaining_budget_bdt",
                                                              "direct_hold_cost_savings_bdt", "planning_backlog_attempt_days",
                                                              "end_planning_backlog", "end_hard_backlog", "direct_cash_roi"]]),
                 "Variable-hire payroll uses proportional allocation of served attempts times each hub's historical Delivered/Assigned "
                 "yield, plus BDT 300 for each paid day. The budget reserve instead covers BDT 14 for every effective standard-workload "
                 "attempt being delivered. This upper-bound contract is dearer than fixed pay, so the robust optimisation uses fixed "
                 "contracts; a cheaper variable-pay optimum based on uncertain delivery allowances is not asserted.",
                 "## Q10 - first-14-day controls", markdown_table(tables["risk_register"]),
                 "## Model limitations and audit trail",
                 "Daily demand is spread uniformly within each forecast week because no daily forecast or route/shift schedule is supplied. "
                 "Daily peaks, absenteeism and transfer travel delays could create queues even where weekly averages fit. New hires and "
                 "transfers start day 1; transfers have full productivity in the base and 80% for seven days in a sensitivity. "
                 "Starting backlog is zero because the Phase 1 multiplier already includes carry-in retry flow; adding the 236 still-held "
                 "orders on top would double-count unquantified backlog without an explicit arrival model. The 85% queue is a target-cap "
                 "exposure measure. The 100% queue uses 40 attempts per effective agent-day; neither permits cross-hub pooling. "
                 "No actual delivery event, order, salary or hold was invented. Model inputs are checked against the Phase 1 original-data "
                 "references. SQL and Phase 1 result hashes are preserved in scenario_manifest.json."]
    (STRATEGIC / "STRATEGIC_ANALYSIS.md").write_text("\n\n".join(headline) + "\n", encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
