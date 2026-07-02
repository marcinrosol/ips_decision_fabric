"""Parses the master IPS table-of-contents PDF (1968-2013) into an ordered
per-seminar list of (title, authors). Pure text extraction + regex -- no OCR
needed, this file has a native text layer.

Best-effort: format varies a lot across 45 years of proceedings (title-first
vs. authors-first, page numbers present or absent, alternate header wording
for a few joint/renamed conferences). Seminars where no reliable page-number
markers are found simply yield an empty entry list rather than a guess."""

import re
from pathlib import Path

import fitz

SECTION_RE = re.compile(
    r"(\d+)(?:st|nd|rd|th)\s+(?:IPS\s+|International\s+Pyrotechnics\s+)?Seminar\b[^\n]*?(\d{4})"
)
PAGE_MARKER_RE = re.compile(r"\n(\d+)\s*\n")


def _split_title_authors(blob: str) -> tuple[str, str]:
    """Titles in the 1968-2000-ish entries end with a period before the
    author list ('Title text. Surname A, Surname B'). Later volumes list
    authors first with no clean separator -- when the split doesn't look
    like a real title/author pair, we fall back to treating the whole blob
    as the title (still enough distinctive text for matching purposes)."""
    blob = re.sub(r"\s+", " ", blob).strip()
    idx = blob.rfind(". ")
    if idx != -1:
        title, tail = blob[:idx].strip(), blob[idx + 2 :].strip()
        if len(title) >= 10 and len(tail) <= 120:
            return title, tail
    return blob, ""


def _parse_entries(block: str) -> list[tuple[str, str]]:
    markers = list(PAGE_MARKER_RE.finditer(block))
    entries = []
    prev_end = 0
    for marker in markers:
        chunk = block[prev_end : marker.start()]
        prev_end = marker.end()
        chunk = re.sub(r"^\s*\d+\s+", "", chunk, count=1)
        title, authors = _split_title_authors(chunk)
        if title:
            entries.append((title, authors))
    return entries


def parse(pdf_path: Path) -> dict[int, list[tuple[str, str]]]:
    doc = fitz.open(pdf_path)
    try:
        text = "\n".join(doc[i].get_text() for i in range(len(doc)))
    finally:
        doc.close()

    sections = list(SECTION_RE.finditer(text))
    result: dict[int, list[tuple[str, str]]] = {}
    for i, section in enumerate(sections):
        seminar_number = int(section.group(1))
        block_start = section.end()
        block_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        result[seminar_number] = _parse_entries(text[block_start:block_end])
    return result
