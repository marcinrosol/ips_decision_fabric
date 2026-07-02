"""Backfills article_title/article_authors metadata onto chunks already in
the vector store, by matching the master IPS table-of-contents against each
seminar's already-ingested chunk text. No PDF re-parsing beyond the master
TOC file itself, no re-OCR, no re-embedding -- a pure metadata patch, safe
to rerun.

Usage:
    python -m pipeline.backfill_articles [--only SUBSTR] [--dry-run]
                                          [--master-toc PATH] [--corpus-dir PATH]
                                          [--persist-dir PATH] [--collection-name NAME]
"""

import argparse
import re
from pathlib import Path

from pipeline import master_toc, store
from pipeline.articles import ChunkRecord, assign_articles

CORPUS_DIR = Path(__file__).parent.parent / "data" / "corpus"
MASTER_TOC_PATH = CORPUS_DIR / "IPS-TOC-1968-2013.pdf"

FILENAME_RE = re.compile(r"^(\d+)-IPS-(\d{4})-.*?(?:-(?:Part|Volume)-(\d+))?\.pdf$", re.IGNORECASE)


def _seminar_files(corpus_dir: Path) -> dict[int, list[Path]]:
    """Groups corpus PDFs by seminar number, ordering split-volume parts
    (Part-1/Part-2, Volume-1/Volume-2) so their chunks concatenate in the
    right reading order."""
    grouped: dict[int, list[tuple[int, Path]]] = {}
    for path in corpus_dir.glob("*.pdf"):
        match = FILENAME_RE.match(path.name)
        if not match:
            continue
        seminar_number = int(match.group(1))
        part = int(match.group(3)) if match.group(3) else 1
        grouped.setdefault(seminar_number, []).append((part, path))
    return {num: [p for _, p in sorted(parts)] for num, parts in grouped.items()}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backfill article-level citation metadata onto ingested chunks.")
    p.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    p.add_argument("--master-toc", type=Path, default=MASTER_TOC_PATH)
    p.add_argument("--persist-dir", type=Path, default=store.DEFAULT_PERSIST_DIR)
    p.add_argument("--collection-name", type=str, default=store.DEFAULT_COLLECTION_NAME)
    p.add_argument("--only", type=str, default=None, help="Only process seminars/filenames containing this substring.")
    p.add_argument(
        "--exclude-seminars", type=str, default=None,
        help="Comma-separated seminar numbers to skip entirely (e.g. volumes with known poor match quality).",
    )
    p.add_argument("--dry-run", action="store_true", help="Print match stats without writing.")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    toc_by_seminar = master_toc.parse(args.master_toc)
    seminar_files = _seminar_files(args.corpus_dir)
    collection = store.get_collection(args.persist_dir, args.collection_name)
    excluded = {int(n) for n in args.exclude_seminars.split(",")} if args.exclude_seminars else set()

    for seminar_number in sorted(seminar_files):
        if seminar_number in excluded:
            print(f"[pipeline] seminar {seminar_number}: excluded, skipping")
            continue
        titles = toc_by_seminar.get(seminar_number, [])
        if not titles:
            continue
        files = seminar_files[seminar_number]
        if args.only and not any(args.only in f.name for f in files):
            continue

        rows: list[dict] = []
        for f in files:
            rows.extend(store.list_chunks_for_source(collection, f.name))
        if not rows:
            continue

        chunks = [ChunkRecord(id=r["id"], text=r["document"]) for r in rows]
        assignments = assign_articles(chunks, titles)
        matched_titles = len({title for title, _ in assignments.values()})
        names = ", ".join(f.name for f in files)
        print(
            f"[pipeline] seminar {seminar_number} ({names}): "
            f"{len(assignments)}/{len(rows)} chunks matched to "
            f"{matched_titles}/{len(titles)} articles"
        )
        if not args.dry_run:
            store.update_article_metadata(collection, assignments)

    print("[pipeline] backfill finished" + (" (dry run, nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
