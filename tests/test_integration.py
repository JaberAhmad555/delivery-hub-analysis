import sqlite3

import pandas as pd
import pytest

from src.analysis import run_queries
from src.config import RAW, HEADERS
from src.load_data import build_database, read_sources
from src.validation import validate_results, validate_sources

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def originals():
    if not all((RAW / f"{name}.csv").exists() for name in HEADERS):
        pytest.skip("Original assessment CSVs unavailable; run python -m src.download_data")
    return read_sources()


@pytest.fixture(scope="module")
def verified(originals, tmp_path_factory):
    path = tmp_path_factory.mktemp("database") / "assessment.sqlite3"
    audit = build_database(RAW, path)
    with sqlite3.connect(path) as connection:
        results = run_queries(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0] == 8
    return audit, results


def test_source_counts_and_all_independent_results(originals, verified):
    audit, results = verified
    assert audit["matched_attempts"] == 25595
    assert audit["event_join_rows"] == 51190
    assert audit["source_integrity"] == "passed"
    check = validate_results(originals, results)
    assert check["original_reference_checks"] == "passed"
    assert len(check["independent_comparisons"]) == 8


def test_daily_outcome_reconciliation(verified):
    daily = verified[1]["q1_agent_day"]
    assert daily.attempts.eq(daily.delivered + daily.holds + daily.returned).all()
    assert len(daily) == 882


def test_forecast_complete_and_historical_cost_reconciliation(verified):
    results = verified[1]
    assert len(results["q7_staffing_forecast"]) == 24
    assert results["q7_staffing_forecast"].groupby("hub_id").size().eq(4).all()
    costs = results["q6_delivery_costs"]
    assert costs.operating_cost_bdt.eq(costs.staffing_pay_bdt + costs.hold_cost_bdt + costs.return_cost_bdt).all()


@pytest.mark.parametrize("mutation,match", [
    ("duplicate_agent", "duplicate key"), ("duplicate_assignment", "Duplicate Assigned"),
    ("missing_outcome", "matching"), ("wrong_agent", "attribution"), ("wrong_hub", "hub mismatch"),
    ("orphan_order", "Orphan"), ("early_join", "before joining"), ("inactive_departure", "departure"),
    ("bad_reason", "Unknown hold"), ("third_hold", "Third attempt"),
    ("wrong_final", "Final status"), ("bad_forecast", "Forecast grid"), ("wrong_rule", "policy rules"),
])
def test_source_audit_rejects_corruption(originals, mutation, match):
    frames = {name: frame.copy(deep=True) for name, frame in originals.items()}
    logs = frames["order_logs"]
    first_assignment = logs[logs.status.eq("Assigned")].iloc[0]
    outcome_index = logs.index[logs.order_id.eq(first_assignment.order_id) & logs.attempt_no.eq(first_assignment.attempt_no) & logs.status.ne("Assigned")][0]
    if mutation == "duplicate_agent":
        frames["agents"] = pd.concat([frames["agents"], frames["agents"].iloc[[0]]])
    elif mutation == "duplicate_assignment":
        duplicate = logs[logs.log_id.eq(first_assignment.log_id)].copy()
        duplicate["log_id"] = "TEST_DUPLICATE"
        frames["order_logs"] = pd.concat([logs, duplicate])
    elif mutation == "missing_outcome":
        frames["order_logs"] = logs.drop(outcome_index)
    elif mutation == "wrong_agent":
        other = frames["agents"].query("agent_id != @first_assignment.agent_id").iloc[0].agent_id
        logs.loc[outcome_index, "agent_id"] = other
    elif mutation == "wrong_hub":
        agent_row = frames["agents"].agent_id.eq(first_assignment.agent_id)
        original_hub = frames["agents"].loc[agent_row, "hub_id"].iloc[0]
        frames["agents"].loc[agent_row, "hub_id"] = "H02" if original_hub == "H01" else "H01"
    elif mutation == "orphan_order":
        logs.loc[outcome_index, "order_id"] = "UNKNOWN"
    elif mutation == "early_join":
        frames["agents"].loc[frames["agents"].agent_id.eq(first_assignment.agent_id), "joining_date"] = "2026-10-27"
    elif mutation == "inactive_departure":
        agent = logs.loc[logs.event_time.ge("2026-10-20"), "agent_id"].iloc[0]
        frames["agents"].loc[frames["agents"].agent_id.eq(agent), "active_status"] = "Inactive"
    elif mutation == "bad_reason":
        logs.loc[logs.status.eq("Hold"), "hold_reason"] = "Unclassified"
    elif mutation == "third_hold":
        idx = logs.index[logs.attempt_no.eq(3) & logs.status.ne("Assigned")][0]
        logs.loc[idx, ["status", "hold_reason"]] = ["Hold", "Late Dispatch"]
    elif mutation == "wrong_final":
        frames["orders"].loc[0, "final_status"] = "Hold" if frames["orders"].loc[0, "final_status"] != "Hold" else "Delivered"
    elif mutation == "bad_forecast":
        frames["volume_forecast"] = frames["volume_forecast"].iloc[1:]
    elif mutation == "wrong_rule":
        frames["rules"].loc[0, "value"] = "41"
    with pytest.raises(ValueError, match=match):
        validate_sources(frames)


def test_failed_rebuild_keeps_previous_database(originals, tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for name, frame in originals.items():
        frame.to_csv(raw_dir / f"{name}.csv", index=False)
    database = tmp_path / "existing.sqlite3"
    database.write_bytes(b"previous database sentinel")
    bad = originals["agents"].copy()
    bad.loc[0, "hub_id"] = "UNKNOWN"
    bad.to_csv(raw_dir / "agents.csv", index=False)
    with pytest.raises(ValueError, match="Orphan"):
        build_database(raw_dir, database)
    assert database.read_bytes() == b"previous database sentinel"
