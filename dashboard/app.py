"""Flask app: dashboard page + /api/state JSON endpoint.

Usage (from repo root): python -m dashboard.app
"""

import asyncio
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from agents import loop as agent_loop
from dashboard import actions, queries

app = Flask(__name__)

STALE_SECONDS = 15

# In-memory chat history for the dashboard's single chat panel -- process-wide,
# not per-browser-session. Resets on dashboard restart or /api/chat/reset.
# Guarded by a lock since Flask's dev server handles requests on multiple
# threads.
_chat_history: list[dict] = []
_chat_lock = threading.Lock()


def _is_running(updated_at: str | None) -> bool:
    if not updated_at:
        return False
    updated = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - updated).total_seconds() < STALE_SECONDS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    sim_status = queries.get_sim_status()
    payload = {
        "sim_status": {**sim_status, "running": _is_running(sim_status["updated_at"])} if sim_status else None,
        "inventory": queries.get_inventory_status(),
        "events": queries.get_recent_events(),
        "pending_decisions": queries.get_pending_decisions(),
        "draft_purchase_orders": queries.get_draft_purchase_orders(),
        "pending_experiments": queries.get_pending_experiments(),
        "experiments_timeline": queries.get_experiment_timeline(),
    }
    return jsonify(payload)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    message = (request.get_json(silent=True) or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    with _chat_lock:
        history = list(_chat_history)

    result = asyncio.run(agent_loop.answer(message, history=history))

    with _chat_lock:
        _chat_history[:] = result["history"]

    return jsonify({"response": result["response"], "tool_calls": result["tool_calls"]})


@app.route("/api/chat/reset", methods=["POST"])
def api_chat_reset():
    with _chat_lock:
        _chat_history.clear()
    return jsonify({"ok": True})


def _require_reviewer() -> str | tuple:
    body = request.get_json(silent=True) or {}
    reviewer = body.get("reviewer", "").strip()
    if not reviewer:
        return None, (jsonify({"error": "reviewer is required"}), 400)
    return reviewer, body


@app.route("/api/decisions/<int:decision_id>/approve", methods=["POST"])
def approve_decision_route(decision_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    actions.approve_decision(decision_id, reviewer, body.get("outcome"))
    return jsonify({"ok": True})


@app.route("/api/decisions/<int:decision_id>/override", methods=["POST"])
def override_decision_route(decision_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    outcome = (body.get("outcome") or "").strip()
    if not outcome:
        return jsonify({"error": "outcome is required for an override"}), 400
    actions.override_decision(decision_id, reviewer, outcome)
    return jsonify({"ok": True})


@app.route("/api/purchase-orders/<int:po_id>/approve", methods=["POST"])
def approve_po_route(po_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    actions.approve_purchase_order(po_id, reviewer)
    return jsonify({"ok": True})


@app.route("/api/purchase-orders/<int:po_id>/reject", methods=["POST"])
def reject_po_route(po_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    actions.reject_purchase_order(po_id, reviewer)
    return jsonify({"ok": True})


@app.route("/api/experiments/<int:schedule_id>/approve", methods=["POST"])
def approve_experiment_route(schedule_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    actions.approve_experiment(schedule_id, reviewer)
    return jsonify({"ok": True})


@app.route("/api/experiments/<int:schedule_id>/reject", methods=["POST"])
def reject_experiment_route(schedule_id):
    reviewer, body = _require_reviewer()
    if reviewer is None:
        return body
    actions.reject_experiment(schedule_id, reviewer)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=False, host=os.environ.get("DASHBOARD_HOST", "127.0.0.1"), port=5000)
