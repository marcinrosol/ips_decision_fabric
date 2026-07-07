"""Read-only queries backing the dashboard's /api/state endpoint. Each
function opens its own short-lived connection (query_only, closed after
use) -- simplest safe pattern given Flask's dev server is multi-threaded
and the simulation engine is writing to the same DB concurrently (WAL mode).
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "inventory" / "inventory.db"

# PO statuses that mean "something is already in motion for this chemical" --
# used both to suppress the needs-ordering icon and to show the truck icon.
ACTIVE_PO_STATUSES = ("Submitted", "Approved", "Shipped", "Backordered")
IN_TRANSIT_PO_STATUSES = ("Submitted", "Approved", "Shipped")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_sim_status(db_path: Path = DB_PATH) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM Sim_State WHERE id = 1").fetchone()
        if row is None:
            return None
        state = dict(row)
        horizon = conn.execute(
            """SELECT MIN(d) AS min_d, MAX(d) AS max_d FROM (
                   SELECT scheduled_date AS d FROM Experiment_Schedule
                   UNION ALL SELECT order_date AS d FROM Purchase_Order
                   UNION ALL SELECT expected_delivery_date AS d FROM Purchase_Order
                       WHERE expected_delivery_date IS NOT NULL
               )"""
        ).fetchone()
        state["horizon_start"] = horizon["min_d"]
        state["horizon_end"] = horizon["max_d"]
        return state
    finally:
        conn.close()


def get_inventory_status(db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        chemicals = [
            dict(r)
            for r in conn.execute(
                """SELECT chemical_id, name, category, quantity_on_hand, unit_of_measure, reorder_threshold
                   FROM Chemical ORDER BY name"""
            )
        ]
        placeholders = ",".join("?" for _ in ACTIVE_PO_STATUSES)
        po_rows = conn.execute(
            f"SELECT chemical_id, status FROM Purchase_Order WHERE status IN ({placeholders})",
            ACTIVE_PO_STATUSES,
        ).fetchall()
    finally:
        conn.close()

    statuses_by_chemical: dict[int, set] = {}
    for r in po_rows:
        statuses_by_chemical.setdefault(r["chemical_id"], set()).add(r["status"])

    result = []
    for c in chemicals:
        qty = c["quantity_on_hand"]
        threshold = c["reorder_threshold"]
        if qty <= threshold:
            level = "red"
        elif qty <= 2 * threshold:
            level = "yellow"
        else:
            level = "green"

        statuses = statuses_by_chemical.get(c["chemical_id"], set())
        c["level"] = level
        c["in_transit"] = bool(statuses & set(IN_TRANSIT_PO_STATUSES))
        c["delayed"] = "Backordered" in statuses
        c["needs_ordering"] = level == "red" and not statuses
        result.append(c)
    return result


def get_recent_events(limit: int = 50, db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM Sim_Event_Log ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_decisions(limit: int = 20, db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM Decision_Log WHERE human_decision = 'Pending' ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_draft_purchase_orders(db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT po.*, c.name AS chemical_name FROM Purchase_Order po
               JOIN Chemical c ON c.chemical_id = po.chemical_id
               WHERE po.status = 'Draft' ORDER BY po.order_date DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_experiment_timeline(db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT schedule_id, experiment_code, title, objective, lead_chemist,
                      scheduled_date, duration_minutes, test_site, risk_level, status,
                      approval_status, approved_by, ips_reference_citation
               FROM Experiment_Schedule ORDER BY scheduled_date"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_experiments(db_path: Path = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM Experiment_Schedule WHERE approval_status = 'Pending' ORDER BY scheduled_date"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
