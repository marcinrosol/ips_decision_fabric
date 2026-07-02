"""Chroma persistent vector store helpers -- the only module that talks to
Chroma directly."""

from pathlib import Path

import chromadb

from pipeline.chunk import Chunk
from pipeline.citations import build_citation

DEFAULT_PERSIST_DIR = Path(__file__).parent.parent / "data" / "vector_store" / "chroma"
DEFAULT_COLLECTION_NAME = "ips_proceedings"


def get_collection(persist_dir: Path = DEFAULT_PERSIST_DIR, collection_name: str = DEFAULT_COLLECTION_NAME):
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(collection_name)


def already_ingested(collection, source_file: str) -> bool:
    existing = collection.get(where={"source_file": source_file}, limit=1)
    return len(existing["ids"]) > 0


def delete_source(collection, source_file: str) -> None:
    collection.delete(where={"source_file": source_file})


def list_chunks_for_source(collection, source_file: str) -> list[dict]:
    """Returns this file's chunks (id, document, metadata) sorted by id --
    the zero-padded chunk index in add_chunks' id scheme makes id order the
    same as original reading order."""
    result = collection.get(where={"source_file": source_file}, include=["documents", "metadatas"])
    rows = [
        {"id": id_, "document": doc, "metadata": meta}
        for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]
    rows.sort(key=lambda r: r["id"])
    return rows


def update_article_metadata(collection, article_by_chunk_id: dict[str, tuple[str, str]]) -> None:
    """Patches article_title/article_authors onto existing chunk metadata
    without touching embeddings or documents."""
    if not article_by_chunk_id:
        return
    existing = collection.get(ids=list(article_by_chunk_id.keys()), include=["metadatas"])
    metadatas = []
    for id_, meta in zip(existing["ids"], existing["metadatas"]):
        title, authors = article_by_chunk_id[id_]
        metadatas.append({**meta, "article_title": title, "article_authors": authors})
    collection.update(ids=existing["ids"], metadatas=metadatas)


def add_chunks(
    collection,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    source_file: str,
    seminar_number: int,
    year: int,
) -> None:
    if not chunks:
        return
    ids = [f"{source_file}::{i:05d}" for i in range(len(chunks))]
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "source_file": source_file,
            "seminar_number": seminar_number,
            "year": year,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "citation": build_citation(seminar_number, year, c.page_start, c.page_end),
            "extraction_method": c.extraction_method,
        }
        for c in chunks
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
