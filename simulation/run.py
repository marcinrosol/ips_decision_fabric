"""CLI entry point for the live simulation engine.

Usage:
    python simulation/run.py [--speed-factor 1440] [--tick-seconds 2] [--seed N]
                              [--max-sim-days N] [--max-real-seconds N] [--db-path PATH]
"""

import argparse
import random
import time
from pathlib import Path

from simulation import db as db_module
from simulation import engine, state
from simulation.clock import SimClock, dates_between


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the IPS Decision Fabric live-state simulation engine.")
    p.add_argument(
        "--speed-factor", type=float, default=1440.0,
        help="Simulated seconds per real second (default 1440 = 1 sim day per 60 real sec).",
    )
    p.add_argument(
        "--tick-seconds", type=float, default=2.0,
        help="Real-time interval between engine wake-ups (default 2s).",
    )
    p.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducible stochastic events (default: OS entropy on first run).",
    )
    p.add_argument(
        "--max-sim-days", type=int, default=None,
        help="Stop after processing this many new sim-days (default: run indefinitely).",
    )
    p.add_argument(
        "--max-real-seconds", type=float, default=None,
        help="Stop after this many real seconds regardless of sim-days processed.",
    )
    p.add_argument(
        "--db-path", type=Path, default=db_module.DB_PATH,
        help="Path to inventory.db (default: data/inventory/inventory.db).",
    )
    p.add_argument(
        "--start-sim-date", type=str, default=None,
        help="Sim_State.sim_now on first run only, 'YYYY-MM-DD HH:MM:SS' (default: 2026-06-30 00:00:00). Ignored on resume.",
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    conn = db_module.connect(args.db_path)

    row = state.load_or_init(conn, args.speed_factor, args.seed, args.start_sim_date)
    conn.execute("UPDATE Sim_State SET speed_factor = ? WHERE id = 1", (args.speed_factor,))

    rng = random.Random(row["random_seed"])
    clock = SimClock.parse(row["sim_now"], args.speed_factor)
    last_processed = row["last_processed_sim_date"]

    print(f"[sim] Starting at sim_now={clock.sim_now_str()} speed_factor={args.speed_factor} seed={row['random_seed']}")
    if last_processed:
        print(
            f"[sim] Resuming: last_processed_sim_date={last_processed}, "
            f"total_sim_days_processed={row['total_sim_days_processed']}"
        )

    sim_days_processed_this_run = 0
    real_start = time.monotonic()

    try:
        while True:
            if args.max_real_seconds is not None and (time.monotonic() - real_start) >= args.max_real_seconds:
                print("[sim] Reached --max-real-seconds, stopping.")
                break
            if args.max_sim_days is not None and sim_days_processed_this_run >= args.max_sim_days:
                print("[sim] Reached --max-sim-days, stopping.")
                break

            time.sleep(args.tick_seconds)
            clock = clock.advance(args.tick_seconds)
            state.save_sim_now(conn, clock.sim_now_str())

            for sim_date in dates_between(last_processed, clock.sim_date()):
                if args.max_sim_days is not None and sim_days_processed_this_run >= args.max_sim_days:
                    break
                engine.run_sim_day(conn, sim_date, rng)
                last_processed = sim_date
                sim_days_processed_this_run += 1
    except KeyboardInterrupt:
        print("\n[sim] Interrupted, shutting down cleanly.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
