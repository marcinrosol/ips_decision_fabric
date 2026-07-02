"""Orchestrates one PDF: extract -> chunk -> embed -> store."""

from pathlib import Path

from pipeline import store
from pipeline.chunk import chunk_pages
from pipeline.citations import parse_filename
from pipeline.embed import EmbeddingModel
from pipeline.extract import extract_pages

EMBED_BATCH_SIZE = 64


def ingest_document(
    pdf_path: Path,
    collection,
    embedder: EmbeddingModel,
    ocr_dpi: int = 200,
    ocr_workers: int = 1,
    chunk_words: int = 400,
    chunk_overlap: int = 60,
    log=print,
) -> int:
    """Ingests one PDF into collection, returns the number of chunks added.
    Returns 0 (with a log message) for filenames that don't match the
    seminar-volume naming pattern."""
    parsed = parse_filename(pdf_path.name)
    if parsed is None:
        log(f"[pipeline] {pdf_path.name}: skipped (doesn't match seminar volume naming)")
        return 0
    seminar_number, year = parsed

    pages = extract_pages(pdf_path, ocr_dpi=ocr_dpi, workers=ocr_workers, log=log)
    chunks = chunk_pages(
        [(p.page_number, p.text, p.method) for p in pages],
        chunk_words=chunk_words,
        overlap_words=chunk_overlap,
    )
    if not chunks:
        log(f"[pipeline] {pdf_path.name}: no extractable text, 0 chunks")
        return 0

    embeddings = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        embeddings.extend(embedder.encode([c.text for c in batch]))

    store.add_chunks(collection, chunks, embeddings, pdf_path.name, seminar_number, year)
    ocr_pages = sum(1 for p in pages if p.method == "ocr")
    log(f"[pipeline] {pdf_path.name}: {len(pages)} pages ({ocr_pages} ocr), {len(chunks)} chunks added")
    return len(chunks)
