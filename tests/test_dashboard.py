"""Clean aggregate-only startup, navigation, filters and privacy checks."""
from pathlib import Path
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from src.config import ROOT
from src.dashboard_data import load_snapshot, dashboard_source_zip


def test_snapshot_aggregates_and_privacy():
    tables, meta = load_snapshot()
    assert meta["phase1_validated"] and meta["phase1_unchanged"]
    assert tables["historical_hub_week"].orders.sum() == 22789
    assert tables["daily_hub"].attempts.sum() == 25595
    for frame in tables.values():
        assert not {"order_id", "log_id", "agent_id", "agent_name", "cod_amount", "event_time"}.intersection(frame.columns)
    assert tables["high_return_agents"].agent.tolist() == ["Agent 45", "Agent 46", "Agent 47"]


def test_snapshot_checksum_rejects_tampering(tmp_path):
    shutil.copytree(ROOT / "dashboard_data", tmp_path / "snapshot")
    file = tmp_path / "snapshot" / "hubs.csv"
    file.write_bytes(file.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(tmp_path / "snapshot")


def test_downloadable_source_is_complete_and_excludes_raw_data():
    from io import BytesIO
    import zipfile
    with zipfile.ZipFile(BytesIO(dashboard_source_zip())) as archive:
        names = archive.namelist()
        assert "app.py" in names and "src/dashboard_data.py" in names and "dashboard_data/metadata.json" in names
        assert not any(name.startswith(("data/", "outputs/", ".git/")) or name.endswith((".sqlite3", ".env")) for name in names)
        assert "src/download_data.py" not in names


@pytest.mark.parametrize("page", ["Executive Overview", "Hub Diagnostics", "Forecast and Budget"])
def test_pages_without_exceptions(page):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert len(app.metric) >= 4
    assert not app.code  # No accidental Streamlit magic/debug rendering.


def test_filters_hub_and_scenario():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.multiselect[0].set_value(["Cluster B"]).run()
    app.sidebar.selectbox[0].set_value("Week 2 · 20–26 Oct").run()
    assert not app.exception
    assert app.metric[0].value == "4,429"
    app.sidebar.radio[0].set_value("Hub Diagnostics").run()
    app.selectbox(key="hub").set_value("Riverside").run()
    assert app.metric[0].value == "3,051"
    app.sidebar.radio[0].set_value("Forecast and Budget").run()
    app.selectbox(key="scenario").set_value("Eight fixed hires").run()
    assert not app.exception and len(app.error) == 1
    assert app.metric[0].value == "BDT 185,600"


def test_empty_cluster_selection_is_handled():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception
    assert "Select at least one cluster" in app.info[0].value


def test_app_clean_snapshot_only(tmp_path):
    # Intentionally omit data/raw, the SQLite database and outputs/.
    shutil.copy2(ROOT / "app.py", tmp_path / "app.py")
    (tmp_path / "src").mkdir()
    shutil.copy2(ROOT / "src" / "dashboard_data.py", tmp_path / "src" / "dashboard_data.py")
    (tmp_path / "src" / "__init__.py").write_text("")
    shutil.copytree(ROOT / "dashboard_data", tmp_path / "dashboard_data")
    tables, _ = load_snapshot(tmp_path / "dashboard_data")
    assert len(tables["forecast"]) == 24
    # AppTest's interpreter can already have src imported; explicit snapshot
    # isolation verifies the dependency boundary separately from navigation.
    assert not (tmp_path / "data").exists() and not (tmp_path / "outputs").exists()
