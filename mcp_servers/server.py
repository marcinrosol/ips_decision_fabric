"""MCP server exposing IPS Decision Fabric's two data sources -- the IPS
proceedings vector store and the live inventory DB -- as tools for the
decision agent. Stdio transport.

Usage: python -m mcp_servers.server
"""

import sqlite3
from datetime import date

from mcp.server.fastmcp import FastMCP

from agents.config import get_model
from pipeline import store as vector_store
from pipeline.embed import EmbeddingModel
from simulation import db as db_module

AGENT_MODEL = get_model()

mcp = FastMCP("ips-decision-fabric")

_embedder = EmbeddingModel()
_collection = None
_write_conn: sqlite3.Connection | None = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = vector_store.get_collection()
    return _collection


def _get_write_conn() -> sqlite3.Connection:
    """Long-lived writer connection, matching simulation.db.connect()'s
    design -- this MCP server process lives for the duration of a dashboard
    session, same shape as the simulation engine."""
    global _write_conn
    if _write_conn is None:
        _write_conn = db_module.connect()
    return _write_conn


def _read_connect() -> sqlite3.Connection:
    """Short-lived read-only connection per call, matching
    dashboard/queries.py's pattern -- safe alongside concurrent writers
    under WAL."""
    conn = sqlite3.connect(db_module.DB_PATH, timeout=5.0)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _next_sequence(conn: sqlite3.Connection, table: str, code_column: str, prefix: str, digits: int) -> str:
    year = date.today().year
    rows = conn.execute(
        f"SELECT {code_column} FROM {table} WHERE {code_column} LIKE ?", (f"{prefix}-{year}-%",)
    ).fetchall()
    max_seq = 0
    for r in rows:
        try:
            max_seq = max(max_seq, int(r[code_column].rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{year}-{max_seq + 1:0{digits}d}"


@mcp.tool()
def search_corpus(query: str, n_results: int = 5) -> list[dict]:
    """Search the IPS proceedings corpus for formulation guidance and
    technical background. Returns chunk text with a citation and, where
    known, the source article's title and authors."""
    embeddings = _embedder.encode([query])
    results = _get_collection().query(query_embeddings=embeddings, n_results=n_results)
    hits = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        hits.append(
            {
                "text": doc,
                "citation": meta.get("citation"),
                "article_title": meta.get("article_title"),
                "article_authors": meta.get("article_authors"),
                "year": meta.get("year"),
            }
        )
    return hits


@mcp.tool()
def get_chemical_status(name: str) -> dict | None:
    """Look up a chemical's current stock level, storage, and hazard
    metadata by name (partial, case-insensitive match)."""
    conn = _read_connect()
    try:
        row = conn.execute(
            "SELECT * FROM Chemical WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT 1", (f"%{name}%",)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@mcp.tool()
def list_low_stock_chemicals() -> list[dict]:
    """List all chemicals currently at or below their reorder threshold."""
    conn = _read_connect()
    try:
        rows = conn.execute(
            "SELECT * FROM Chemical WHERE quantity_on_hand <= reorder_threshold ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def get_experiment_schedule(status: str | None = None) -> list[dict]:
    """List scheduled experiments, optionally filtered by status
    (Planned, Approved, In Progress, Completed, Cancelled, Postponed)."""
    conn = _read_connect()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM Experiment_Schedule WHERE status = ? ORDER BY scheduled_date", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM Experiment_Schedule ORDER BY scheduled_date").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def draft_purchase_order(
    chemical_id: int,
    quantity: float,
    supplier_name: str,
    unit_cost: float | None = None,
    expected_delivery_date: str | None = None,
) -> dict:
    """Draft a purchase order for a chemical. Created with status='Draft' --
    a human must review and submit it; this does not place a real order."""
    conn = _get_write_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        po_number = _next_sequence(conn, "Purchase_Order", "po_number", "PO", 4)
        total_cost = unit_cost * quantity if unit_cost is not None else None
        conn.execute(
            """INSERT INTO Purchase_Order (
                po_number, chemical_id, supplier_name, quantity_ordered, unit_cost_usd,
                total_cost_usd, order_date, expected_delivery_date, status, requested_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Draft', 'agent')""",
            (
                po_number,
                chemical_id,
                supplier_name,
                quantity,
                unit_cost,
                total_cost,
                date.today().isoformat(),
                expected_delivery_date,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    row = conn.execute("SELECT * FROM Purchase_Order WHERE po_number = ?", (po_number,)).fetchone()
    return dict(row)


@mcp.tool()
def draft_experiment_schedule(
    title: str,
    lead_chemist: str,
    scheduled_date: str,
    risk_level: str,
    objective: str | None = None,
    chemicals: list[dict] | None = None,
) -> dict:
    """Draft a new experiment. Created with status='Planned' and
    approval_status='Pending' -- a human must approve it before it can run.
    chemicals is a list of {chemical_id, quantity_required, role} entries
    describing what this experiment requires."""
    conn = _get_write_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        experiment_code = _next_sequence(conn, "Experiment_Schedule", "experiment_code", "EXP", 3)
        conn.execute(
            """INSERT INTO Experiment_Schedule (
                experiment_code, title, objective, lead_chemist, scheduled_date,
                risk_level, status, approval_status
            ) VALUES (?, ?, ?, ?, ?, ?, 'Planned', 'Pending')""",
            (experiment_code, title, objective, lead_chemist, scheduled_date, risk_level),
        )
        schedule_id = conn.execute(
            "SELECT schedule_id FROM Experiment_Schedule WHERE experiment_code = ?", (experiment_code,)
        ).fetchone()[0]
        for c in chemicals or []:
            conn.execute(
                """INSERT INTO Experiment_Chemical (schedule_id, chemical_id, quantity_required, role_in_composition)
                   VALUES (?, ?, ?, ?)""",
                (schedule_id, c["chemical_id"], c["quantity_required"], c.get("role")),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    row = conn.execute("SELECT * FROM Experiment_Schedule WHERE schedule_id = ?", (schedule_id,)).fetchone()
    return dict(row)


@mcp.tool()
def log_decision(
    decision_type: str,
    triggering_event: str,
    recommended_action: str,
    vector_store_citations: str | None = None,
    inventory_snapshot_summary: str | None = None,
    confidence_score: float | None = None,
    related_chemical_id: int | None = None,
    related_schedule_id: int | None = None,
    related_po_id: int | None = None,
    rationale: str | None = None,
) -> dict:
    """Log a decision for human review. decision_type must be one of:
    'Reorder Recommendation', 'Experiment Risk Assessment', 'Composition
    Substitution', 'Compliance Flag', 'Schedule Conflict Resolution',
    'Storage Compatibility Flag'. Call this whenever you reach an actionable
    recommendation, whether or not you also drafted a PO or experiment."""
    conn = _get_write_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """INSERT INTO Decision_Log (
                decision_type, related_chemical_id, related_schedule_id, related_po_id,
                triggering_event, vector_store_citations, inventory_snapshot_summary,
                recommended_action, confidence_score, agent_model, human_decision, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)""",
            (
                decision_type,
                related_chemical_id,
                related_schedule_id,
                related_po_id,
                triggering_event,
                vector_store_citations,
                inventory_snapshot_summary,
                recommended_action,
                confidence_score,
                AGENT_MODEL,
                rationale,
            ),
        )
        decision_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    row = conn.execute("SELECT * FROM Decision_Log WHERE decision_id = ?", (decision_id,)).fetchone()
    return dict(row)


if __name__ == "__main__":
    mcp.run()
