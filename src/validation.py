"""Independent source audits and pandas/Python references, with no SQL reuse."""
from collections import Counter
from decimal import Decimal
from fractions import Fraction
import math

import pandas as pd
from pandas.testing import assert_frame_equal

from src.config import AGENT_HOLDS, CUSTOMER_HOLDS, END, START, WEEK2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_sources(frames: dict[str, pd.DataFrame]) -> dict:
    """Reject cardinality, eligibility, chronology and policy-contract violations."""
    keys = {"hubs": ["hub_id"], "agents": ["agent_id"], "orders": ["order_id"],
            "order_logs": ["log_id"], "agent_salary": ["salary_type"], "costs": ["what"],
            "rules": ["rule"], "volume_forecast": ["hub_id", "week_start"]}
    for table, frame in frames.items():
        require(not frame.duplicated(keys[table]).any(), f"{table}: duplicate key")
        for column in frame.columns:
            if column != "hold_reason":
                require(frame[column].notna().all() and frame[column].astype(str).ne("").all(),
                        f"{table}.{column}: missing value")
    for table, columns in {"agents": ["joining_date"], "orders": ["created_at"],
                           "order_logs": ["event_time"], "volume_forecast": ["week_start", "week_end"]}.items():
        for column in columns:
            fmt = "%Y-%m-%d %H:%M:%S" if column in {"created_at", "event_time"} else "%Y-%m-%d"
            parsed = pd.to_datetime(frames[table][column], format=fmt, errors="raise")
            require(parsed.dt.strftime(fmt).eq(frames[table][column]).all(), f"{table}.{column}: noncanonical date")
    a, o, logs = frames["agents"], frames["orders"], frames["order_logs"]
    for child, column, parent, key in [
        (a, "hub_id", frames["hubs"], "hub_id"), (o, "hub_id", frames["hubs"], "hub_id"),
        (logs, "agent_id", a, "agent_id"), (logs, "order_id", o, "order_id"),
        (a, "salary_type", frames["agent_salary"], "salary_type"),
        (frames["volume_forecast"], "hub_id", frames["hubs"], "hub_id"),
    ]:
        require(child[column].isin(parent[key]).all(), f"Orphan foreign key: {column}")
    require(a.active_status.isin(["Active", "Inactive"]).all(), "Unknown active status")
    require(o.final_status.isin(["Delivered", "Returned", "Hold"]).all(), "Unknown final status")
    require(logs.status.isin(["Assigned", "Delivered", "Hold", "Returned"]).all(), "Unknown event status")
    require(logs.attempt_no.isin([1, 2, 3]).all(), "Attempt number must be 1, 2 or 3")
    days = logs.event_time.str[:10]
    require(days.between(START, END).all(), "Events outside assessment window")
    require(o.created_at.str[:10].between(START, END).all(), "Orders outside assessment window")
    held = logs.status.eq("Hold")
    require(logs.loc[held, "hold_reason"].isin(AGENT_HOLDS | CUSTOMER_HOLDS).all(), "Unknown hold reason")
    require(logs.loc[~held, "hold_reason"].eq("").all(), "Hold reason on non-Hold event")
    assigned = logs[logs.status.eq("Assigned")]
    outcomes = logs[~logs.status.eq("Assigned")]
    pair_keys = ["order_id", "attempt_no"]
    require(not assigned.duplicated(pair_keys).any(), "Duplicate Assigned attempt")
    require(not outcomes.duplicated(pair_keys).any(), "Duplicate outcome attempt")
    pairs = assigned.merge(outcomes, on=pair_keys, how="outer", suffixes=("_assigned", "_outcome"),
                           validate="one_to_one", indicator=True)
    require(pairs._merge.eq("both").all(), "Attempt/outcome matching failed")
    require(pairs.agent_id_assigned.eq(pairs.agent_id_outcome).all(), "Attempt/outcome agent attribution mismatch")
    require(pairs.event_time_assigned.le(pairs.event_time_outcome).all(), "Outcome precedes assignment")
    require(pairs.event_time_assigned.str[:10].eq(pairs.event_time_outcome.str[:10]).all(),
            "Cross-day outcome: revisit daily attribution")
    enriched = logs.merge(a, on="agent_id", validate="many_to_one").merge(
        o[["order_id", "hub_id", "created_at"]], on="order_id", suffixes=("_agent", "_order"), validate="many_to_one")
    require(len(enriched) == len(logs), "Join cardinality changed")
    require(enriched.hub_id_agent.eq(enriched.hub_id_order).all(), "Agent/order hub mismatch")
    event_day = enriched.event_time.str[:10]
    require(event_day.ge(enriched.joining_date).all(), "Event before joining date")
    require((enriched.active_status.eq("Active") | event_day.le("2026-10-19")).all(), "Inactive agent event after departure")
    require(event_day.ge(enriched.created_at.str[:10]).all(), "Event before order creation day")
    require(set(outcomes.order_id) == set(o.order_id), "Order missing an outcome")
    ordered = outcomes.sort_values(["order_id", "attempt_no"]).copy()
    require(ordered.groupby("order_id").attempt_no.min().eq(1).all(), "First attempt is not 1")
    require(ordered.groupby("order_id").attempt_no.diff().dropna().eq(1).all(), "Nonconsecutive attempts")
    previous_status = ordered.groupby("order_id").status.shift()
    previous_day = pd.to_datetime(ordered.groupby("order_id").event_time.shift()).dt.normalize()
    repeat = previous_status.notna()
    require(previous_status[repeat].eq("Hold").all(), "Retry after terminal outcome")
    day_diff = (pd.to_datetime(ordered.event_time).dt.normalize() - previous_day).dt.days
    require(day_diff[repeat].eq(1).all(), "Held order not retried on next day")
    require(not (ordered.attempt_no.eq(3) & ordered.status.eq("Hold")).any(), "Third attempt still held")
    last = ordered.drop_duplicates("order_id", keep="last").merge(o, on="order_id", validate="one_to_one")
    require(last.status.eq(last.final_status).all(), "Final status differs from last outcome")
    require(last.loc[last.status.eq("Hold"), "event_time"].str[:10].eq(END).all(), "Unresolved hold before final day")
    f = frames["volume_forecast"]
    starts = pd.date_range("2026-10-27", periods=4, freq="7D").strftime("%Y-%m-%d")
    expected_grid = {(hub, start) for hub in frames["hubs"].hub_id for start in starts}
    require(set(zip(f.hub_id, f.week_start)) == expected_grid, "Forecast grid is not four weeks per hub")
    require((pd.to_datetime(f.week_end) - pd.to_datetime(f.week_start)).dt.days.eq(6).all(), "Forecast week not 7 days")
    require((f.expected_orders.ge(0) & f.expected_orders.mod(1).eq(0)).all(), "Invalid forecast order count")
    rules = frames["rules"].set_index("rule").value.to_dict()
    expected_rules = {"Standard attempts per agent per day": "40", "Target utilisation": "0.85",
                      "Working days per month": "26", "New agent speed in first 7 days": "0.6",
                      "Hold programme removes agent-side holds": "0.5",
                      "Days for the hold programme to reach full effect": "14",
                      "Agents move only within the same cluster": "Yes",
                      "Agents move only out of hubs whose Week 2 utilisation, before the move, is below": "0.75"}
    require(rules == expected_rules, "Source policy rules differ from assessment")
    costs = frames["costs"].set_index("what").amount_bdt.to_dict()
    require(costs == {"A hold": 30, "A return": 55, "Hiring a new agent": 5000,
                      "Moving an agent to another hub": 2000, "Hold reduction programme": 15000},
            "Source costs differ from assessment")
    salaries = frames["agent_salary"].set_index("salary_type")
    require(set(salaries.index) == {"Fixed", "Variable"}, "Unexpected salary types")
    require(salaries.loc["Fixed"].tolist() == [16900, 0, 0] and salaries.loc["Variable"].tolist() == [0, 300, 14],
            "Source salaries differ from assessment")
    for table, columns in {"orders": ["cod_amount", "delivery_charge"], "costs": ["amount_bdt"],
                           "agent_salary": ["monthly_salary", "daily_allowance", "allowance_per_delivery"]}.items():
        require(frames[table][columns].ge(0).all().all(), f"{table}: negative amount")
        require(frames[table][columns].map(math.isfinite).all().all(), f"{table}: nonfinite amount")
    early = enriched[enriched.status.eq("Assigned") & enriched.event_time.lt(enriched.created_at)]
    return {"row_counts": {name: len(frame) for name, frame in frames.items()},
            "active_agents": int(a.active_status.eq("Active").sum()),
            "inactive_agents": int(a.active_status.eq("Inactive").sum()),
            "matched_attempts": len(pairs), "event_join_rows": len(enriched),
            "assigned_before_created_timestamp_same_day": len(early),
            "source_integrity": "passed"}


def reference_results(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Compute assessment results from original CSV frames, never reading SQL views/results."""
    a, o, logs, hubs = (frames[x].copy() for x in ["agents", "orders", "order_logs", "hubs"])
    logs["day"] = logs.event_time.str[:10]
    logs["week"] = logs.day.map(lambda day: 1 if day < WEEK2 else 2)
    logs = logs.merge(o[["order_id", "hub_id"]], on="order_id", validate="many_to_one")
    a = a.merge(hubs[["hub_id", "hub_name"]], on="hub_id", validate="many_to_one")
    counts = Counter(zip(logs.agent_id, logs.day, logs.status))
    daily_rows = []
    for agent in a.itertuples(index=False):
        for day in pd.date_range(START, END).strftime("%Y-%m-%d"):
            if agent.joining_date > day or (agent.active_status == "Inactive" and day >= WEEK2):
                continue
            row = {"day": day, "week": 1 if day < WEEK2 else 2, "agent_id": agent.agent_id,
                   "agent_name": agent.agent_name, "hub_id": agent.hub_id, "hub_name": agent.hub_name,
                   "salary_type": agent.salary_type}
            for name, status in [("attempts", "Assigned"), ("delivered", "Delivered"), ("holds", "Hold"), ("returned", "Returned")]:
                row[name] = counts[(agent.agent_id, day, status)]
            daily_rows.append(row)
    daily = pd.DataFrame(daily_rows)
    results = {"q1_agent_day": daily}
    rules = frames["rules"].set_index("rule").value.to_dict()
    standard = float(rules["Standard attempts per agent per day"])
    target = float(rules["Target utilisation"])
    salary = frames["agent_salary"].set_index("salary_type").to_dict("index")
    costs = frames["costs"].set_index("what").amount_bdt.to_dict()
    summaries, utilisation, hold_rows, held_rows, cost_rows, forecast_rows = [], [], [], [], [], []
    ever_held = set(logs.loc[logs.status.eq("Hold"), "order_id"])
    for hub in hubs.itertuples(index=False):
        hd = daily[daily.hub_id.eq(hub.hub_id)]
        hl = logs[logs.hub_id.eq(hub.hub_id)]
        summaries.append({"hub_id": hub.hub_id, "available_agent_days": len(hd), "delivered": int(hd.delivered.sum()),
                          "avg_deliveries_per_agent_day": hd.delivered.mean()})
        for week in [1, 2]:
            wd = hd[hd.week.eq(week)]
            attempts = int(wd.attempts.sum())
            rate = attempts / (len(wd) * standard) if len(wd) else None
            utilisation.append({"hub_id": hub.hub_id, "week": week, "attempts": attempts,
                                "eligible_agents": wd.agent_id.nunique(), "available_agent_days": len(wd),
                                "standard_capacity": len(wd) * standard, "utilisation": rate,
                                "target_utilisation": target, "target_breach": int(rate > target) if rate is not None else None,
                                "week2_target_breach": int(rate > target) if week == 2 and rate is not None else 0})
            fixed = allowance = delivery_pay = Decimal(0)
            for day in wd.itertuples(index=False):
                pay = salary[day.salary_type]
                fixed += Decimal(str(pay["monthly_salary"])) / Decimal(rules["Working days per month"])
                allowance += Decimal(str(pay["daily_allowance"]))
                delivery_pay += Decimal(str(pay["allowance_per_delivery"])) * int(day.delivered)
            hc = Decimal(str(costs["A hold"])) * int(wd.holds.sum())
            rc = Decimal(str(costs["A return"])) * int(wd.returned.sum())
            staffing = fixed + allowance + delivery_pay
            total = staffing + hc + rc
            delivered = int(wd.delivered.sum())
            cost_rows.append({"hub_id": hub.hub_id, "week": week, "paid_agent_days": len(wd), "delivered_orders": delivered,
                              "fixed_salary_bdt": float(fixed), "daily_allowances_bdt": float(allowance),
                              "delivery_allowances_bdt": float(delivery_pay), "hold_cost_bdt": float(hc), "return_cost_bdt": float(rc),
                              "staffing_pay_bdt": float(staffing), "operating_cost_bdt": float(total),
                              "cost_per_delivered_order_bdt": float(total / delivered) if delivered else None})
        holds = hl[hl.week.eq(2) & hl.status.eq("Hold")]
        reasons = sorted(Counter(holds.hold_reason).items(), key=lambda item: (-item[1], item[0]))
        agent_count = int(holds.hold_reason.isin(AGENT_HOLDS).sum())
        hold_row = {"hub_id": hub.hub_id, "total_holds": len(holds), "agent_side_holds": agent_count,
                    "agent_side_share": agent_count / len(holds) if len(holds) else None}
        for rank in [1, 2]:
            reason, count = reasons[rank-1] if len(reasons) >= rank else (None, None)
            hold_row[f"top_reason_{rank}"] = reason
            hold_row[f"top_reason_{rank}_count"] = count
        hold_rows.append(hold_row)
        cohort = o[o.hub_id.eq(hub.hub_id) & o.order_id.isin(ever_held)]
        held_row = {"hub_id": hub.hub_id, "ever_held_orders": len(cohort)}
        for name, status in [("delivered", "Delivered"), ("returned", "Returned"), ("still_held", "Hold")]:
            number = int(cohort.final_status.eq(status).sum())
            held_row[f"{name}_orders"] = number
            held_row[f"{name}_share"] = number / len(cohort) if len(cohort) else None
        held_rows.append(held_row)
        w2_attempts = int((hl.status.eq("Assigned") & hl.week.eq(2)).sum())
        w2_orders = len(o[o.hub_id.eq(hub.hub_id) & o.created_at.str[:10].ge(WEEK2)])
        workforce = len(a[a.hub_id.eq(hub.hub_id) & a.active_status.eq("Active") & a.joining_date.le(END)])
        for f in frames["volume_forecast"].query("hub_id == @hub.hub_id").itertuples(index=False):
            days = (pd.Timestamp(f.week_end) - pd.Timestamp(f.week_start)).days + 1
            multiplier = Fraction(w2_attempts, w2_orders) if w2_orders else None
            projected = int(f.expected_orders) * multiplier if multiplier is not None else None
            capacity = days * Fraction(rules["Standard attempts per agent per day"]) * Fraction(rules["Target utilisation"])
            needed = math.ceil(projected / capacity) if projected is not None else None
            forecast_rows.append({"hub_id": hub.hub_id, "week_start": f.week_start, "week_end": f.week_end,
                                  "forecast_orders": int(f.expected_orders), "historical_attempts": w2_attempts,
                                  "historical_new_orders": w2_orders, "attempts_per_order": float(multiplier) if multiplier is not None else None,
                                  "expected_attempts": float(projected) if projected is not None else None,
                                  "current_active_agents": workforce, "target_attempts_per_agent_day": standard * target,
                                  "operating_days": days, "required_agents": needed,
                                  "staffing_gap": needed - workforce if needed is not None else None,
                                  "shortage": max(needed - workforce, 0) if needed is not None else None,
                                  "surplus": max(workforce - needed, 0) if needed is not None else None})
    metrics = []
    for agent in a.itertuples(index=False):
        al = logs[logs.agent_id.eq(agent.agent_id)]
        assigned_count = int(al.status.eq("Assigned").sum())
        returns = int(al.status.eq("Returned").sum())
        tenure = (pd.Timestamp(END) - pd.Timestamp(agent.joining_date)).days
        ratio = returns / assigned_count if assigned_count else None
        if tenure > 30 and ratio is not None and ratio > 0.15:
            metrics.append({"agent_id": agent.agent_id, "tenure_days": tenure, "attempts": assigned_count,
                            "returned_attempts": returns, "return_ratio": ratio})
    results.update({"q1_hub_summary": pd.DataFrame(summaries), "q2_utilisation": pd.DataFrame(utilisation),
                    "q3_hold_reasons": pd.DataFrame(hold_rows), "q4_held_orders": pd.DataFrame(held_rows),
                    "q5_high_return_agents": pd.DataFrame(metrics, columns=["agent_id", "tenure_days", "attempts", "returned_attempts", "return_ratio"]),
                    "q6_delivery_costs": pd.DataFrame(cost_rows), "q7_staffing_forecast": pd.DataFrame(forecast_rows)})
    return results


def validate_results(frames: dict, results: dict, check_original: bool = True) -> dict:
    references = reference_results(frames)
    keys = {"q1_agent_day": ["day", "hub_id", "agent_id"], "q1_hub_summary": ["hub_id"],
            "q2_utilisation": ["hub_id", "week"], "q3_hold_reasons": ["hub_id"], "q4_held_orders": ["hub_id"],
            "q5_high_return_agents": ["agent_id"], "q6_delivery_costs": ["hub_id", "week"],
            "q7_staffing_forecast": ["hub_id", "week_start"]}
    comparisons = {}
    for name, reference in references.items():
        expected = reference.sort_values(keys[name]).reset_index(drop=True)
        actual = results[name][expected.columns].sort_values(keys[name]).reset_index(drop=True)
        assert_frame_equal(actual, expected, check_dtype=False, check_exact=False, atol=1e-9, rtol=1e-12)
        comparisons[name] = {"status": "passed", "rows": len(actual), "columns_compared": len(expected.columns)}
    if check_original:
        expected_counts = {"hubs": 6, "agents": 64, "orders": 22789, "order_logs": 51190, "volume_forecast": 24}
        for table, expected in expected_counts.items():
            require(len(frames[table]) == expected, f"Reference row count differs: {table}")
        require(frames["agents"].active_status.value_counts().to_dict() == {"Active": 62, "Inactive": 2}, "Reference active-agent counts differ")
        expected_util = {"Greenfield": 88.64, "Lakeview": 56.17, "Riverside": 90.80,
                         "Hillcrest": 95.87, "Brookside": 71.49, "Westwood": 80.36}
        w2 = results["q2_utilisation"].query("week == 2")
        for row in w2.itertuples(index=False):
            require(round(row.utilisation * 100, 2) == expected_util[row.hub_name], f"Reference utilisation differs: {row.hub_name}")
        riverside = results["q3_hold_reasons"].query("hub_name == 'Riverside'").iloc[0]
        require(riverside.total_holds == 874 and riverside.agent_side_holds == 563, "Riverside hold reference differs")
    return {"independent_comparisons": comparisons, "original_reference_checks": "passed" if check_original else "not requested"}
