"""Small synthetic edge-case fixtures; never used for assessment outputs."""
import sqlite3

import pytest

from src.config import ROOT


@pytest.fixture
def connection():
    db = sqlite3.connect(":memory:")
    db.executescript((ROOT / "sql" / "00_schema.sql").read_text(encoding="utf-8"))
    db.executemany("INSERT INTO hubs VALUES (?, ?, ?)", [("H01", "Test Hub", "Test Cluster"), ("H02", "Empty Hub", "Test Cluster")])
    db.executemany("INSERT INTO agent_salary VALUES (?, ?, ?, ?)", [("Fixed", 16900, 0, 0), ("Variable", 0, 300, 14)])
    db.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?)", [
        ("A1", "Fixed Fixture", "H01", "Fixed", "2026-10-13", "Active"),
        ("A2", "Variable Fixture", "H01", "Variable", "2026-10-20", "Active"),
        ("A3", "Inactive Fixture", "H01", "Fixed", "2026-10-01", "Inactive")])
    db.executemany("INSERT INTO rules VALUES (?, ?)", [("Standard attempts per agent per day", "40"),
                                                        ("Target utilisation", "0.85"), ("Working days per month", "26")])
    db.executemany("INSERT INTO costs VALUES (?, ?, ?)", [("A hold", 30, "Every hold"), ("A return", 55, "Every return")])
    yield db
    db.close()


def add_attempt(db, order, status, day="2026-10-20", agent="A1", attempt=1, reason=None):
    db.execute("INSERT OR IGNORE INTO orders VALUES (?, 'H01', ?, ?, 0, 0)", (order, day + " 06:00:00", status))
    db.execute("UPDATE orders SET final_status = ? WHERE order_id = ?", (status, order))
    db.executemany("INSERT INTO order_logs VALUES (?, ?, ?, ?, ?, ?, ?)", [
        (f"{order}-{attempt}-A", order, agent, "Assigned", None, day + " 08:00:00", attempt),
        (f"{order}-{attempt}-O", order, agent, status, reason, day + " 16:00:00", attempt)])
