"""Sim_State row load/init/save. The row always exists after seed.py has
run; load_or_init's "no row" branch is a defensive fallback, not the
primary path."""

import random
import sqlite3

DEFAULT_SIM_NOW = "2026-06-30 00:00:00"


def load_or_init(
    conn: sqlite3.Connection,
    speed_factor: float,
    seed: int | None,
    start_sim_date: str | None,
) -> dict:
    row = conn.execute("SELECT * FROM Sim_State WHERE id = 1").fetchone()
    if row is not None:
        if start_sim_date:
            print(f"[sim] Resuming existing Sim_State; ignoring --start-sim-date={start_sim_date!r}")
        state = dict(row)
        if state["random_seed"] is None:
            resolved_seed = seed if seed is not None else random.SystemRandom().randint(0, 2**31 - 1)
            conn.execute("UPDATE Sim_State SET random_seed = ? WHERE id = 1", (resolved_seed,))
            state["random_seed"] = resolved_seed
        return state

    sim_now = start_sim_date or DEFAULT_SIM_NOW
    resolved_seed = seed if seed is not None else random.SystemRandom().randint(0, 2**31 - 1)
    conn.execute(
        "INSERT INTO Sim_State (id, sim_now, speed_factor, random_seed) VALUES (1, ?, ?, ?)",
        (sim_now, speed_factor, resolved_seed),
    )
    return dict(conn.execute("SELECT * FROM Sim_State WHERE id = 1").fetchone())


def save_sim_now(conn: sqlite3.Connection, sim_now_str: str) -> None:
    conn.execute("UPDATE Sim_State SET sim_now = ?, updated_at = datetime('now') WHERE id = 1", (sim_now_str,))
