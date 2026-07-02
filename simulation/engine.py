"""DB I/O and transaction orchestration: fetches rows, delegates to the pure
functions in events.py, and applies the resulting instructions -- plus a
matching Sim_Event_Log row for each -- in one transaction per sim-day.
"""

import random
import sqlite3

from simulation import events


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def _log_event(conn, sim_date, event_type, entity_type, entity_id, message, log):
    conn.execute(
        """INSERT INTO Sim_Event_Log (sim_date, event_type, entity_type, entity_id, message)
           VALUES (?, ?, ?, ?, ?)""",
        (sim_date, event_type, entity_type, entity_id, message),
    )
    log(f"[{sim_date} sim] {message}")


def _advance_experiments(conn, sim_date, log):
    in_progress = _rows(conn.execute("SELECT schedule_id, experiment_code FROM Experiment_Schedule WHERE status = 'In Progress'"))
    for change in events.plan_experiment_completions(in_progress):
        conn.execute(
            "UPDATE Experiment_Schedule SET status = ? WHERE schedule_id = ?",
            (change.new_status, change.schedule_id),
        )
        _log_event(
            conn, sim_date, "ExperimentCompleted", "Experiment_Schedule", change.schedule_id,
            f"{change.experiment_code} -> Completed", log,
        )

    candidates = _rows(
        conn.execute(
            """SELECT schedule_id, experiment_code, status, approval_status, scheduled_date
               FROM Experiment_Schedule WHERE status IN ('Planned', 'Approved')"""
        )
    )

    for change in events.plan_experiment_starts(candidates, sim_date):
        experiment_chemicals = _rows(
            conn.execute(
                """SELECT ec.chemical_id, c.name AS chemical_name, ec.quantity_required, c.quantity_on_hand
                   FROM Experiment_Chemical ec JOIN Chemical c ON c.chemical_id = ec.chemical_id
                   WHERE ec.schedule_id = ?""",
                (change.schedule_id,),
            )
        )
        depletions = events.plan_depletions(experiment_chemicals)
        parts = []
        for d in depletions:
            conn.execute(
                "UPDATE Chemical SET quantity_on_hand = quantity_on_hand + ? WHERE chemical_id = ?",
                (d.delta, d.chemical_id),
            )
            parts.append(f"{d.chemical_name} {d.delta:+.2f}kg" + (" (clamped)" if d.clamped else ""))

        conn.execute(
            "UPDATE Experiment_Schedule SET status = ? WHERE schedule_id = ?",
            (change.new_status, change.schedule_id),
        )
        depletion_summary = ", ".join(parts) if parts else "no linked chemicals"
        _log_event(
            conn, sim_date, "ExperimentStarted", "Experiment_Schedule", change.schedule_id,
            f"{change.experiment_code} -> In Progress; depleted {depletion_summary}", log,
        )

    for experiment in events.plan_pending_approval_warnings(candidates, sim_date):
        _log_event(
            conn, sim_date, "ApprovalPending", "Experiment_Schedule", experiment["schedule_id"],
            f"{experiment['experiment_code']} is due ({experiment['scheduled_date']}) but still awaiting approval", log,
        )


def _advance_purchase_orders(conn, sim_date, rng: random.Random, log):
    pos = _rows(
        conn.execute(
            """SELECT po_id, po_number, chemical_id, quantity_ordered, status, order_date, expected_delivery_date
               FROM Purchase_Order WHERE status NOT IN ('Received', 'Cancelled')"""
        )
    )
    for po in pos:
        change = events.plan_po_transition(po, sim_date, rng)
        if change is None:
            continue

        conn.execute(
            """UPDATE Purchase_Order
               SET status = ?,
                   actual_delivery_date = COALESCE(?, actual_delivery_date),
                   expected_delivery_date = COALESCE(?, expected_delivery_date)
               WHERE po_id = ?""",
            (change.new_status, change.actual_delivery_date, change.expected_delivery_date, change.po_id),
        )

        if change.new_status == "Received":
            conn.execute(
                "UPDATE Chemical SET quantity_on_hand = quantity_on_hand + ? WHERE chemical_id = ?",
                (po["quantity_ordered"], po["chemical_id"]),
            )

        if change.new_status != po["status"]:
            event_type = "Backordered" if change.new_status == "Backordered" else "POTransition"
            message = f"{change.po_number} {po['status']} -> {change.new_status}"
        else:
            event_type = "SupplierDelay"
            message = f"{change.po_number} delayed; new expected delivery {change.expected_delivery_date}"

        _log_event(conn, sim_date, event_type, "Purchase_Order", change.po_id, message, log)


def _roll_stochastic_events(conn, sim_date, rng: random.Random, log):
    chemicals = _rows(conn.execute("SELECT chemical_id, name, quantity_on_hand FROM Chemical"))
    for adj in events.plan_recount_adjustments(chemicals, sim_date, rng):
        conn.execute(
            "UPDATE Chemical SET quantity_on_hand = quantity_on_hand + ?, last_inventory_check = ? WHERE chemical_id = ?",
            (adj.delta, adj.new_last_inventory_check, adj.chemical_id),
        )
        _log_event(
            conn, sim_date, "StochasticRecount", "Chemical", adj.chemical_id,
            f"{adj.chemical_name} recount adjustment {adj.delta:+.2f}kg", log,
        )


def _handle_expirations(conn, sim_date, log):
    chemicals = _rows(
        conn.execute(
            """SELECT chemical_id, name, expiration_date, notes FROM Chemical
               WHERE expiration_date IS NOT NULL AND expiration_date <= ?
                 AND (notes IS NULL OR notes NOT LIKE '%[EXPIRED%')""",
            (sim_date,),
        )
    )
    for flag in events.plan_expirations(chemicals, sim_date):
        conn.execute(
            "UPDATE Chemical SET notes = COALESCE(notes, '') || ? WHERE chemical_id = ?",
            (f" [EXPIRED {sim_date}]", flag.chemical_id),
        )
        _log_event(
            conn, sim_date, "Expiration", "Chemical", flag.chemical_id,
            f"{flag.chemical_name} passed its expiration date ({flag.expiration_date})", log,
        )


def run_sim_day(conn: sqlite3.Connection, sim_date: str, rng: random.Random, log=print) -> None:
    """Applies one sim-day's worth of state changes in a single transaction.
    Idempotent per sim_date via the Sim_State.last_processed_sim_date guard
    checked by the caller (simulation/run.py) before invoking this."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _advance_experiments(conn, sim_date, log)
        _advance_purchase_orders(conn, sim_date, rng, log)
        _roll_stochastic_events(conn, sim_date, rng, log)
        _handle_expirations(conn, sim_date, log)
        conn.execute(
            """UPDATE Sim_State
               SET last_processed_sim_date = ?,
                   total_sim_days_processed = total_sim_days_processed + 1,
                   updated_at = datetime('now')
               WHERE id = 1""",
            (sim_date,),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
