"""Pure sim-time <-> wall-time math. No I/O."""

from dataclasses import dataclass
from datetime import datetime, timedelta

SIM_DATE_FMT = "%Y-%m-%d"
SIM_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class SimClock:
    sim_now: datetime
    speed_factor: float  # simulated seconds per real second

    def advance(self, real_elapsed_seconds: float) -> "SimClock":
        """Return a new SimClock advanced by the sim-time equivalent of a
        real-time elapsed interval."""
        return SimClock(
            sim_now=self.sim_now + timedelta(seconds=real_elapsed_seconds * self.speed_factor),
            speed_factor=self.speed_factor,
        )

    def sim_date(self) -> str:
        return self.sim_now.strftime(SIM_DATE_FMT)

    def sim_now_str(self) -> str:
        return self.sim_now.strftime(SIM_DATETIME_FMT)

    @staticmethod
    def parse(sim_now_str: str, speed_factor: float) -> "SimClock":
        return SimClock(sim_now=datetime.strptime(sim_now_str, SIM_DATETIME_FMT), speed_factor=speed_factor)


def dates_between(start_date: str, end_date: str) -> list[str]:
    """All sim-dates strictly after start_date, up to and including end_date,
    as 'YYYY-MM-DD' strings. Used to walk every sim-day boundary crossed in
    a single tick, even if the tick advanced sim time by more than one day."""
    start = datetime.strptime(start_date, SIM_DATE_FMT) if start_date else None
    end = datetime.strptime(end_date, SIM_DATE_FMT)
    if start is None:
        return [end.strftime(SIM_DATE_FMT)]
    dates = []
    current = start + timedelta(days=1)
    while current <= end:
        dates.append(current.strftime(SIM_DATE_FMT))
        current += timedelta(days=1)
    return dates
