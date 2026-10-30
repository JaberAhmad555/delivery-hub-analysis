import pandas as pd
import pytest

from src.analysis import run_queries
from tests.conftest import add_attempt


def test_zero_activity_and_staff_eligibility(connection):
    daily = run_queries(connection)["q1_agent_day"]
    assert len(daily) == 28
    assert daily.attempts.sum() == 0
    assert daily.query("agent_id == 'A2'").day.min() == "2026-10-20"
    assert daily.query("agent_id == 'A3'").day.max() == "2026-10-19"
    assert len(daily.query("agent_id == 'A1'")) == 14


@pytest.mark.parametrize("day,week", [("2026-10-13", 1), ("2026-10-19", 1), ("2026-10-20", 2), ("2026-10-26", 2)])
def test_week_boundaries(connection, day, week):
    add_attempt(connection, "O1", "Delivered", day)
    result = run_queries(connection)["q2_utilisation"].query("hub_id == 'H01'").set_index("week")
    assert result.loc[week, "attempts"] == 1
    assert result.loc[3 - week, "attempts"] == 0
    assert result.loc[week, "available_agent_days"] == 14


@pytest.mark.parametrize("attempts,breach", [(238, 0), (239, 1)])
def test_utilisation_target_is_strict(connection, attempts, breach):
    connection.execute("DELETE FROM agents WHERE agent_id != 'A1'")
    for n in range(attempts):
        add_attempt(connection, f"O{n}", "Delivered")
    row = run_queries(connection)["q2_utilisation"].query("hub_id == 'H01' and week == 2").iloc[0]
    assert row.utilisation == pytest.approx(attempts / 280)
    assert row.week2_target_breach == breach


def test_hold_classification_and_ties(connection):
    for i, reason in enumerate(["Late Dispatch", "Not Attempted", "Agent Time Shortage", "Customer Unreachable"]):
        add_attempt(connection, f"O{i}", "Hold", reason=reason)
    row = run_queries(connection)["q3_hold_reasons"].query("hub_id == 'H01'").iloc[0]
    assert row.total_holds == 4 and row.agent_side_holds == 3
    assert row.agent_side_share == 0.75
    assert (row.top_reason_1, row.top_reason_2) == ("Agent Time Shortage", "Customer Unreachable")


def test_repeated_holds_count_as_one_order(connection):
    add_attempt(connection, "O1", "Hold", "2026-10-20", attempt=1, reason="Late Dispatch")
    add_attempt(connection, "O1", "Hold", "2026-10-21", attempt=2, reason="Not Attempted")
    add_attempt(connection, "O1", "Delivered", "2026-10-22", attempt=3)
    add_attempt(connection, "O2", "Hold", "2026-10-26", reason="Customer Unreachable")
    row = run_queries(connection)["q4_held_orders"].query("hub_id == 'H01'").iloc[0]
    assert row.ever_held_orders == 2 and row.delivered_orders == 1 and row.still_held_orders == 1
    assert row.delivered_share == row.still_held_share == 0.5


@pytest.mark.parametrize("joining,returns,qualifies", [("2026-09-25", 4, True), ("2026-09-26", 4, False), ("2026-09-25", 3, False)])
def test_return_and_tenure_strict_thresholds(connection, joining, returns, qualifies):
    connection.execute("UPDATE agents SET joining_date = ? WHERE agent_id = 'A1'", (joining,))
    for n in range(20):
        add_attempt(connection, f"O{n}", "Returned" if n < returns else "Delivered")
    result = run_queries(connection)["q5_high_return_agents"]
    assert (len(result) == 1) == qualifies
    if qualifies:
        assert result.iloc[0].attempts == 20 and result.iloc[0].returned_attempts == 4


def test_costs_pay_zero_activity_staff(connection):
    add_attempt(connection, "O1", "Delivered", agent="A2")
    add_attempt(connection, "O2", "Delivered", agent="A2")
    add_attempt(connection, "O3", "Hold", agent="A2", reason="Late Dispatch")
    add_attempt(connection, "O4", "Returned", agent="A2")
    results = run_queries(connection)["q6_delivery_costs"].query("hub_id == 'H01'").set_index("week")
    assert results.loc[1, "fixed_salary_bdt"] == 14 * 650
    assert results.loc[2, "fixed_salary_bdt"] == 7 * 650  # fixed agent has no attempts
    assert results.loc[2, "daily_allowances_bdt"] == 7 * 300
    assert results.loc[2, "delivery_allowances_bdt"] == 28
    assert results.loc[2, "hold_cost_bdt"] == 30 and results.loc[2, "return_cost_bdt"] == 55
    assert results.loc[2, "operating_cost_bdt"] == 6763
    assert results.loc[2, "cost_per_delivered_order_bdt"] == 3381.5
    assert pd.isna(results.loc[1, "cost_per_delivered_order_bdt"])


def test_empty_hub_has_counts_but_undefined_rates(connection):
    results = run_queries(connection)
    assert results["q2_utilisation"].query("hub_id == 'H02'").utilisation.isna().all()
    assert results["q3_hold_reasons"].query("hub_id == 'H02'").agent_side_share.isna().all()
    assert results["q4_held_orders"].query("hub_id == 'H02'").delivered_share.isna().all()
    assert results["q6_delivery_costs"].query("hub_id == 'H02'").cost_per_delivered_order_bdt.isna().all()


@pytest.mark.parametrize("orders,needed", [(0, 0), (1, 1), (119, 1), (120, 2), (238, 2), (239, 3)])
def test_forecast_attempt_multiplier_and_ceiling(connection, orders, needed):
    add_attempt(connection, "O1", "Hold", reason="Late Dispatch")
    add_attempt(connection, "O1", "Delivered", day="2026-10-21", attempt=2)
    connection.execute("INSERT INTO volume_forecast VALUES ('H01', '2026-10-27', '2026-11-02', ?)", (orders,))
    row = run_queries(connection)["q7_staffing_forecast"].iloc[0]
    assert row.attempts_per_order == 2
    assert row.expected_attempts == orders * 2
    assert row.operating_days == 7 and row.current_active_agents == 2
    assert row.required_agents == needed
    assert row.staffing_gap == needed - 2


def test_forecast_without_history_is_unknown(connection):
    connection.execute("INSERT INTO volume_forecast VALUES ('H02', '2026-10-27', '2026-11-02', 100)")
    row = run_queries(connection)["q7_staffing_forecast"].iloc[0]
    assert pd.isna(row.required_agents) and pd.isna(row.shortage) and pd.isna(row.surplus)


def test_unique_outcome_index_blocks_join_fanout(connection):
    import sqlite3
    add_attempt(connection, "O1", "Delivered")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO order_logs VALUES ('duplicate', 'O1', 'A1', 'Returned', NULL, '2026-10-20 17:00:00', 1)")
