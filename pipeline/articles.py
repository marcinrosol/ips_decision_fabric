"""Fuzzy-matches a seminar's ordered article title list (from
master_toc.parse()) against chunks already sitting in the vector store, to
assign each chunk an article attribution without re-touching the source
PDFs. Pure -- no I/O."""

import re
from dataclasses import dataclass

MATCH_THRESHOLD = 0.6
MIN_SIGNIFICANT_WORD_LEN = 4
LOOKAHEAD_TITLES = 5  # tolerate a few unmatched/annex entries in a row
MAX_SIMULTANEOUS_MATCHES = 2  # more than this means it's a contents/index page, not body text


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) >= MIN_SIGNIFICANT_WORD_LEN}


@dataclass
class ChunkRecord:
    id: str
    text: str


def assign_articles(
    chunks: list[ChunkRecord], titles: list[tuple[str, str]]
) -> dict[str, tuple[str, str]]:
    """chunks must be in original reading order. Scans forward through both
    sequences in lockstep: once a title's significant words are found with
    enough overlap in a chunk (checked against a small forward window so a
    never-appearing annex entry doesn't stall the scan), every chunk from
    there until the next confirmed title inherits that article. Chunks
    before the first match get no entry -- favors leaving a chunk
    unattributed over guessing wrong.

    Guards against the volume's own front-matter table of contents, which
    lists every article's title in quick succession -- a chunk landing on
    that page will score >=threshold against many titles at once, not just
    the next expected one. A real body chunk should only ever plausibly
    match one (rarely two, e.g. adjacent short papers in one chunk) titles,
    so a chunk matching more than MAX_SIMULTANEOUS_MATCHES is treated as an
    index/contents page and skipped rather than accepted."""
    title_words = [(_significant_words(title), title, authors) for title, authors in titles]

    result: dict[str, tuple[str, str]] = {}
    title_idx = 0
    current: tuple[str, str] | None = None

    for chunk in chunks:
        chunk_words = _significant_words(chunk.text)
        if chunk_words and title_idx < len(title_words):
            window_end = min(title_idx + LOOKAHEAD_TITLES, len(title_words))
            candidates = []
            for candidate_idx in range(title_idx, window_end):
                words, title, authors = title_words[candidate_idx]
                if not words:
                    continue
                overlap = len(words & chunk_words) / len(words)
                if overlap >= MATCH_THRESHOLD:
                    candidates.append(candidate_idx)
            if 1 <= len(candidates) <= MAX_SIMULTANEOUS_MATCHES:
                candidate_idx = candidates[0]
                _, title, authors = title_words[candidate_idx]
                current = (title, authors)
                title_idx = candidate_idx + 1
        if current is not None:
            result[chunk.id] = current
    return result
