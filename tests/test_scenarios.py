"""Scenario identities, eligibility, costs, timing and original-data outcomes."""
from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from src.config import RAW, OUTPUTS
from src.scenario_analysis import (Assumptions, Plan, evaluate, programme_ramp, queue_path, load_model,
                                   validate_plan, budget_rows, optimise, phase1_hashes)


@pytest.fixture(scope="module")
def model():
    if not (RAW / "orders.csv").exists():
        pytest.skip("Original assessment CSVs required for scenario integration checks")
    return load_model()


@pytest.fixture
def plan():
    return Plan("Test combination", (0, 0, 0, 2, 0, 0), (("H02", "H01", 2),), ("H03",))


def test_hold_delay_and_linear_ramp():
    delayed = programme_ramp(Assumptions())
    assert np.all(delayed[:14] == 0) and np.all(delayed[14:] == .5)
    linear = programme_ramp(Assumptions(ramp="linear"))
    assert linear[0] == 0 and linear[14] == .5 and linear[7] == .25
    assert np.all(np.diff(linear) >= 0)


@pytest.mark.parametrize("assumptions", [Assumptions(ramp="instant"), Assumptions(programme_effectiveness=1.1), Assumptions(programme_delay=-1)])
def test_invalid_ramp(assumptions):
    with pytest.raises(ValueError):
        programme_ramp(assumptions)


def test_queue_conservation_and_no_pooling():
    demand = np.array([[12., 6., 0.], [0., 0., 0.]])
    capacity = np.array([[10., 5., 10.], [20., 20., 20.]])
    backlog, served = queue_path(demand, capacity)
    np.testing.assert_allclose(backlog[0], [2, 3, 0])
    np.testing.assert_allclose(np.cumsum(demand - served, axis=1), backlog)
    assert served[1].sum() == 0


@pytest.mark.parametrize("transfers,message", [
    ((("H02", "H03", 1),), "same cluster"), ((("H03", "H04", 1),), "below 75%"),
    ((("H02", "H01", 12),), "more existing"), ((("H02", "H01", 1), ("H02", "H01", 1)), "Duplicate"),
])
def test_ineligible_transfers(model, transfers, message):
    with pytest.raises(ValueError, match=message):
        validate_plan(model, Plan("Invalid", transfers=transfers))


def test_transfer_exact_75_percent_rejected(model):
    changed = replace(model, utilisation=model.utilisation.copy())
    changed.utilisation.loc["H02", "utilisation"] = .75
    with pytest.raises(ValueError, match="strictly below"):
        validate_plan(changed, Plan("Threshold", transfers=(("H02", "H01", 1),)))


def test_salary_days_and_budget_do_not_net_off_savings(model, plan):
    score28, _ = evaluate(model, plan)
    score26, _ = evaluate(model, plan, Assumptions(payroll_days=26))
    assert score28["one_time_cost_bdt"] == 29000
    assert score28["new_payroll_estimate_bdt"] == 36400
    assert score28["budget_reserved_bdt"] == 65400 and score28["remaining_budget_bdt"] == 4600
    assert score26["budget_reserved_bdt"] == 62800
    assert score28["budget_reserved_bdt"] - score26["budget_reserved_bdt"] == 2 * 2 * 650
    assert score28["budget_reserved_bdt"] > score28["total_incremental_cash_cost_bdt"]
    assert budget_rows(model, plan).amount_bdt.sum() == 70000


def test_first_seven_days_productivity_does_not_reduce_salary(model, plan):
    _, weekly = evaluate(model, plan)
    hill = weekly.query("hub_id == 'H04'")
    np.testing.assert_allclose(hill.effective_agent_days, [71.4, 77, 77, 77])
    low, _ = evaluate(model, plan, Assumptions(first_week_productivity=.4))
    normal, _ = evaluate(model, plan)
    assert low["new_payroll_estimate_bdt"] == normal["new_payroll_estimate_bdt"]
    assert low["planning_backlog_attempt_days"] > normal["planning_backlog_attempt_days"]


def test_one_hold_one_saving_one_lagged_retry(model, plan):
    score, weekly = evaluate(model, plan)
    assert score["avoided_hold_events"] == pytest.approx(score["avoided_reattempts_in_horizon"] + score["avoided_retries_after_horizon"])
    assert score["direct_hold_cost_savings_bdt"] == pytest.approx(score["avoided_hold_events"] * 30)
    assert score["recognised_incremental_revenue_bdt"] == 0
    first = weekly.query("forecast_week <= 2")
    assert first.avoided_holds.sum() == first.avoided_reattempts.sum() == 0
    river = weekly.query("hub_id == 'H03'")
    assert river.iloc[2].avoided_reattempts == pytest.approx(river.iloc[2].avoided_holds * 6 / 7)
    assert weekly.query("hub_id != 'H03'").avoided_holds.sum() == 0


def test_cost_and_roi_identity(model, plan):
    s, _ = evaluate(model, plan)
    total = s["one_time_cost_bdt"] + s["new_payroll_estimate_bdt"]
    assert s["incremental_operating_cost_bdt"] == pytest.approx(s["new_payroll_estimate_bdt"] - s["direct_hold_cost_savings_bdt"])
    assert s["total_incremental_cash_cost_bdt"] == pytest.approx(total - s["direct_hold_cost_savings_bdt"])
    assert s["direct_cash_roi"] == pytest.approx((s["direct_hold_cost_savings_bdt"] - total) / total)


def test_variable_allowances_are_reserved(model):
    s, _ = evaluate(model, Plan("Variable", (0, 0, 0, 2, 0, 0), salary_type="Variable"))
    assert s["new_fixed_salary_bdt"] == 0
    assert s["new_daily_allowance_bdt"] == 2 * 28 * 300
    assert s["new_payroll_reserve_bdt"] >= s["new_payroll_estimate_bdt"]
    assert s["new_payroll_reserve_bdt"] == pytest.approx(2 * (28 * 300 + (21 + 7 * .6) * 40 * 14))


def test_demand_and_programme_sensitivities(model, plan):
    base, _ = evaluate(model, plan)
    high, _ = evaluate(model, plan, Assumptions(demand_factor=1.2))
    half, _ = evaluate(model, plan, Assumptions(programme_effectiveness=.5))
    linear, _ = evaluate(model, plan, Assumptions(ramp="linear"))
    assert high["planning_backlog_attempt_days"] > base["planning_backlog_attempt_days"]
    assert half["direct_hold_cost_savings_bdt"] == pytest.approx(base["direct_hold_cost_savings_bdt"] / 2)
    assert linear["direct_hold_cost_savings_bdt"] > base["direct_hold_cost_savings_bdt"]
    assert high["budget_reserved_bdt"] == base["budget_reserved_bdt"]


def test_planning_queue_is_not_hard_backlog(model, plan):
    base, _ = evaluate(model, Plan("Baseline"))
    s, _ = evaluate(model, plan)
    assert s["planning_backlog_attempt_days"] > 0 and s["hard_backlog_attempt_days"] == 0
    assert base["end_hard_backlog"] == 0
    assert s["planning_backlog_attempt_days"] < base["planning_backlog_attempt_days"]


def test_eight_hires_exceed_budget(model):
    s, _ = evaluate(model, Plan("Eight", (2, 0, 3, 3, 0, 0)))
    assert s["budget_reserved_bdt"] == 185600
    assert not s["budget_feasible"]


def test_all_hubs_all_four_weeks_and_conservation(model, plan):
    s, weekly = evaluate(model, plan)
    assert len(weekly) == 24 and weekly.groupby("hub_id").size().eq(4).all()
    assert weekly.groupby("forecast_week").roster_agents.sum().eq(64).all()
    assert weekly.required_attempts_after_programme.sum() == pytest.approx(s["required_attempts"])
    assert s["served_attempts_at_standard"] + s["end_hard_backlog"] == pytest.approx(s["required_attempts"])


def test_exhaustive_robust_optimum(model, plan):
    best, info = optimise(model)
    assert best.hires == plan.hires and best.transfers == plan.transfers and best.programmes == plan.programmes
    assert info["feasible_plans_evaluated"] == 2864
    assert info["best"]["budget_reserved_bdt"] <= 70000


def test_saved_phase1_hashes_unchanged():
    path = OUTPUTS / "strategic" / "scenario_manifest.json"
    if not path.exists():
        pytest.skip("Run scenarios before checking their input manifest")
    expected = json.loads(path.read_text())["phase1_sha256"]
    assert phase1_hashes() == expected
