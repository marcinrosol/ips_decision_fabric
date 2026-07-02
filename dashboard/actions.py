"""Write actions for the human-review workflow: approving/rejecting agent
decisions, drafted purchase orders, and drafted experiments. Short-lived
connection per action -- infrequent and human-triggered, unlike
queries.py's read-only connections or the agent's long-lived MCP writer
(mcp_servers/server.py)."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "inventory" / "inventory.db"


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def approve_decision(decision_id: int, reviewer: str, outcome: str | None = None) -> None:
    conn = _connect()
    try:
        conn.execute(
            """UPDATE Decision_Log SET human_decision = 'Approved', human_reviewer = ?, outcome = ?
               WHERE decision_id = ? AND human_decision = 'Pending'""",
            (reviewer, outcome, decision_id),
        )
        conn.commit()
    finally:
        conn.close()


def override_decision(decision_id: int, reviewer: str, outcome: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            """UPDATE Decision_Log SET human_decision = 'Overridden', human_reviewer = ?, outcome = ?
               WHERE decision_id = ? AND human_decision = 'Pending'""",
            (reviewer, outcome, decision_id),
        )
        conn.commit()
    finally:
        conn.close()


def approve_purchase_order(po_id: int, reviewer: str) -> None:
    """Draft -> Submitted (not straight to Approved) -- Submitted is the
    status simulation/events.py's plan_po_transition already knows how to
    carry forward through the rest of the PO lifecycle."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE Purchase_Order SET status = 'Submitted', approved_by = ? WHERE po_id = ? AND status = 'Draft'",
            (reviewer, po_id),
        )
        conn.commit()
    finally:
        conn.close()


def reject_purchase_order(po_id: int, reviewer: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE Purchase_Order SET status = 'Cancelled', approved_by = ? WHERE po_id = ? AND status = 'Draft'",
            (reviewer, po_id),
        )
        conn.commit()
    finally:
        conn.close()


def approve_experiment(schedule_id: int, reviewer: str) -> None:
    """Only approval_status changes -- status stays 'Planned'.
    plan_experiment_starts already checks approval_status == 'Approved'
    independently of status, so nothing else needs to change here."""
    conn = _connect()
    try:
        conn.execute(
            """UPDATE Experiment_Schedule SET approval_status = 'Approved', approved_by = ?
               WHERE schedule_id = ? AND approval_status = 'Pending'""",
            (reviewer, schedule_id),
        )
        conn.commit()
    finally:
        conn.close()


def reject_experiment(schedule_id: int, reviewer: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            """UPDATE Experiment_Schedule SET approval_status = 'Rejected', approved_by = ?
               WHERE schedule_id = ? AND approval_status = 'Pending'""",
            (reviewer, schedule_id),
        )
        conn.commit()
    finally:
        conn.close()
