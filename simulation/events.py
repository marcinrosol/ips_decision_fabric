"""Pure decision functions for one sim-day. No DB I/O here -- everything
takes plain dicts/lists and (where relevant) a random.Random instance, and
returns dataclass instructions for engine.py to apply. This is what makes
the simulation logic testable without touching SQLite.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

DATE_FMT = "%Y-%m-%d"

# Tunable rates/offsets, gathered here for easy adjustment.
PO_SUBMITTED_TO_APPROVED_DAYS = 2
PO_SHIP_LEAD_DAYS = 5
PO_BACKORDER_FORCE_RECOVERY_DAYS = 10
PO_SUPPLIER_DELAY_PROB = 0.03
PO_SUPPLIER_DELAY_MIN_DAYS = 1
PO_SUPPLIER_DELAY_MAX_DAYS = 5
PO_BACKORDER_PROB = 0.02
PO_BACKORDER_RECOVERY_PROB = 0.05
CHEMICAL_RECOUNT_PROB = 0.01
CHEMICAL_RECOUNT_MAX_PCT = 0.03


def _parse(d: str) -> datetime:
    return datetime.strptime(d, DATE_FMT)


def _days_between(d1: str, d2: str) -> int:
    """Days from d1 to d2 (positive if d2 is later)."""
    return (_parse(d2) - _parse(d1)).days


def _add_days(d: str, n: int) -> str:
    return (_parse(d) + timedelta(days=n)).strftime(DATE_FMT)


@dataclass
class InventoryDepletion:
    chemical_id: int
    delta: float  # negative
    chemical_name: str
    clamped: bool = False  # True if required quantity exceeded stock on hand


@dataclass
class ExperimentStatusChange:
    schedule_id: int
    new_status: str
    experiment_code: str


@dataclass
class POStatusChange:
    po_id: int
    po_number: str
    new_status: str
    actual_delivery_date: str | None = None
    expected_delivery_date: str | None = None


@dataclass
class InventoryAdjustment:
    chemical_id: int
    delta: float
    chemical_name: str
    new_last_inventory_check: str


@dataclass
class ExpirationFlag:
    chemical_id: int
    chemical_name: str
    expiration_date: str


def plan_experiment_completions(in_progress_experiments: list[dict]) -> list[ExperimentStatusChange]:
    """Every experiment already 'In Progress' at the start of the sim-day
    completes today (complete-then-promote ordering guarantees >=1 sim-day
    residency without a dedicated duration column)."""
    return [
        ExperimentStatusChange(
            schedule_id=e["schedule_id"], new_status="Completed", experiment_code=e["experiment_code"]
        )
        for e in in_progress_experiments
    ]


def plan_experiment_starts(candidates: list[dict], sim_date: str) -> list[ExperimentStatusChange]:
    """Planned/Approved experiments that have cleared human approval and
    whose scheduled_date has arrived move to In Progress today."""
    return [
        ExperimentStatusChange(schedule_id=e["schedule_id"], new_status="In Progress", experiment_code=e["experiment_code"])
        for e in candidates
        if e["status"] in ("Planned", "Approved")
        and e["approval_status"] == "Approved"
        and e["scheduled_date"] <= sim_date
    ]


def plan_pending_approval_warnings(candidates: list[dict], sim_date: str) -> list[dict]:
    """Experiments whose scheduled_date has arrived but are still waiting on
    human/agent approval. Not mutated by the engine -- just surfaced."""
    return [
        e
        for e in candidates
        if e["status"] in ("Planned", "Approved")
        and e["approval_status"] == "Pending"
        and e["scheduled_date"] <= sim_date
    ]


def plan_depletions(experiment_chemicals: list[dict]) -> list[InventoryDepletion]:
    """Called once, when an experiment transitions to In Progress, for each
    linked Experiment_Chemical row (each dict must carry chemical_id,
    chemical_name, quantity_required, and the chemical's current
    quantity_on_hand). Depletion is clamped at 0 -- deciding whether to
    block a run on insufficient stock is an agent decision, not this
    engine's."""
    result = []
    for ec in experiment_chemicals:
        current = ec["quantity_on_hand"]
        required = ec["quantity_required"]
        delta = -min(required, current)
        result.append(
            InventoryDepletion(
                chemical_id=ec["chemical_id"],
                delta=delta,
                chemical_name=ec["chemical_name"],
                clamped=required > current,
            )
        )
    return result


def plan_po_transition(po: dict, sim_date: str, rng: random.Random) -> POStatusChange | None:
    """Deterministic day-offset lifecycle with stochastic delay/backorder
    overlaid. Draft/Cancelled/Received are terminal from the engine's
    perspective -- Draft requires a human to submit, Cancelled is a
    human/agent decision, Received is the end state."""
    status = po["status"]
    if status in ("Draft", "Cancelled", "Received"):
        return None

    order_date = po["order_date"]
    expected = po["expected_delivery_date"]

    if status == "Shipped":
        if rng.random() < PO_BACKORDER_PROB:
            return POStatusChange(po_id=po["po_id"], po_number=po["po_number"], new_status="Backordered")
        if expected and sim_date >= expected:
            return POStatusChange(
                po_id=po["po_id"], po_number=po["po_number"], new_status="Received", actual_delivery_date=sim_date
            )
        if expected and rng.random() < PO_SUPPLIER_DELAY_PROB:
            new_expected = _add_days(expected, rng.randint(PO_SUPPLIER_DELAY_MIN_DAYS, PO_SUPPLIER_DELAY_MAX_DAYS))
            return POStatusChange(
                po_id=po["po_id"], po_number=po["po_number"], new_status="Shipped", expected_delivery_date=new_expected
            )
        return None

    if status == "Backordered":
        if expected and _days_between(expected, sim_date) >= PO_BACKORDER_FORCE_RECOVERY_DAYS:
            return POStatusChange(po_id=po["po_id"], po_number=po["po_number"], new_status="Shipped")
        if rng.random() < PO_BACKORDER_RECOVERY_PROB:
            return POStatusChange(po_id=po["po_id"], po_number=po["po_number"], new_status="Shipped")
        return None

    if status == "Submitted":
        if _days_between(order_date, sim_date) >= PO_SUBMITTED_TO_APPROVED_DAYS:
            return POStatusChange(po_id=po["po_id"], po_number=po["po_number"], new_status="Approved")
        return None

    if status == "Approved":
        if expected and rng.random() < PO_SUPPLIER_DELAY_PROB:
            new_expected = _add_days(expected, rng.randint(PO_SUPPLIER_DELAY_MIN_DAYS, PO_SUPPLIER_DELAY_MAX_DAYS))
            return POStatusChange(
                po_id=po["po_id"], po_number=po["po_number"], new_status="Approved", expected_delivery_date=new_expected
            )
        if expected and sim_date >= _add_days(expected, -PO_SHIP_LEAD_DAYS):
            return POStatusChange(po_id=po["po_id"], po_number=po["po_number"], new_status="Shipped")
        return None

    return None


def plan_recount_adjustments(chemicals: list[dict], sim_date: str, rng: random.Random) -> list[InventoryAdjustment]:
    """Rolls a small independent chance per chemical per sim-day of a
    physical-recount discrepancy (noise for the agent layer to react to)."""
    result = []
    for c in chemicals:
        if rng.random() >= CHEMICAL_RECOUNT_PROB:
            continue
        pct = rng.uniform(-CHEMICAL_RECOUNT_MAX_PCT, CHEMICAL_RECOUNT_MAX_PCT)
        delta = c["quantity_on_hand"] * pct
        if c["quantity_on_hand"] + delta < 0:
            delta = -c["quantity_on_hand"]
        result.append(
            InventoryAdjustment(
                chemical_id=c["chemical_id"], delta=delta, chemical_name=c["name"], new_last_inventory_check=sim_date
            )
        )
    return result


def plan_expirations(chemicals: list[dict], sim_date: str) -> list[ExpirationFlag]:
    """Chemicals whose expiration_date has passed and aren't already
    flagged (checked here defensively; engine.py's query does the same
    filter so this rarely has work to do, but staying pure makes it
    testable in isolation)."""
    result = []
    for c in chemicals:
        exp = c.get("expiration_date")
        notes = c.get("notes") or ""
        if exp and exp <= sim_date and "[EXPIRED" not in notes:
            result.append(ExpirationFlag(chemical_id=c["chemical_id"], chemical_name=c["name"], expiration_date=exp))
    return result
