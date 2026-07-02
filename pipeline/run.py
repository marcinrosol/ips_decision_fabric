"""CLI entry point for the IPS proceedings ingestion pipeline.

Usage:
    python -m pipeline.run [--limit N] [--only SUBSTR] [--force]
                            [--workers N] [--ocr-dpi 200]
                            [--chunk-words 400] [--chunk-overlap 60]
                            [--corpus-dir PATH] [--persist-dir PATH]
                            [--collection-name NAME] [--embedding-model NAME]
"""

import argparse
import os
import time
from pathlib import Path

from pipeline import store
from pipeline.embed import DEFAULT_MODEL_NAME, EmbeddingModel
from pipeline.ingest import ingest_document

CORPUS_DIR = Path(__file__).parent.parent / "data" / "corpus"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ingest the IPS proceedings corpus into the vector store.")
    p.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    p.add_argument("--persist-dir", type=Path, default=store.DEFAULT_PERSIST_DIR)
    p.add_argument("--collection-name", type=str, default=store.DEFAULT_COLLECTION_NAME)
    p.add_argument("--embedding-model", type=str, default=DEFAULT_MODEL_NAME)
    p.add_argument("--chunk-words", type=int, default=400)
    p.add_argument("--chunk-overlap", type=int, default=60)
    p.add_argument("--ocr-dpi", type=int, default=200)
    p.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 1))
    p.add_argument("--limit", type=int, default=None, help="Only ingest the first N matched files.")
    p.add_argument("--only", type=str, default=None, help="Only ingest files whose name contains this substring.")
    p.add_argument(
        "--force", action="store_true", help="Re-ingest even if already present (replaces existing chunks)."
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    files = sorted(args.corpus_dir.glob("*.pdf"))
    if args.only:
        files = [f for f in files if args.only in f.name]
    if args.limit is not None:
        files = files[: args.limit]

    collection = store.get_collection(args.persist_dir, args.collection_name)
    embedder = EmbeddingModel(args.embedding_model)

    print(f"[pipeline] {len(files)} candidate files, persist_dir={args.persist_dir}, workers={args.workers}")

    total_chunks = 0
    for pdf_path in files:
        if not args.force and store.already_ingested(collection, pdf_path.name):
            print(f"[pipeline] {pdf_path.name}: already ingested, skipping")
            continue
        if args.force:
            store.delete_source(collection, pdf_path.name)

        start = time.monotonic()
        added = ingest_document(
            pdf_path,
            collection,
            embedder,
            ocr_dpi=args.ocr_dpi,
            ocr_workers=args.workers,
            chunk_words=args.chunk_words,
            chunk_overlap=args.chunk_overlap,
        )
        total_chunks += added
        elapsed = time.monotonic() - start
        if added:
            print(f"[pipeline] {pdf_path.name}: done in {elapsed:.1f}s")

    print(f"[pipeline] finished: {total_chunks} chunks added this run, collection now has {collection.count()} total")


if __name__ == "__main__":
    main()
