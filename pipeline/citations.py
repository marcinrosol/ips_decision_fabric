"""Parses IPS proceedings filenames into citation metadata. Pure -- no I/O."""

import re

FILENAME_RE = re.compile(r"^(\d+)-IPS-(\d{4})-")

_ORDINAL_TEENS = {11, 12, 13}
_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def ordinal(n: int) -> str:
    if n % 100 in _ORDINAL_TEENS:
        suffix = "th"
    else:
        suffix = _ORDINAL_SUFFIXES.get(n % 10, "th")
    return f"{n}{suffix}"


def parse_filename(filename: str) -> tuple[int, int] | None:
    """Returns (seminar_number, year) for a corpus filename like
    '41-IPS-2015-Toulouse-France.pdf', or None if it doesn't match the
    seminar-volume naming pattern (e.g. the TOC index files)."""
    match = FILENAME_RE.match(filename)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def build_citation(seminar_number: int, year: int, page_start: int, page_end: int) -> str:
    return f"Proc. {ordinal(seminar_number)} Int'l Pyrotechnics Seminar ({year}), pp. {page_start}-{page_end}"
