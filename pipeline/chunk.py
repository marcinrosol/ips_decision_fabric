"""Pure text chunking with page-range tracking, for citation purposes. No
I/O -- takes plain page texts, returns plain chunk dataclasses."""

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    page_start: int
    page_end: int
    extraction_method: str  # "native", "ocr", or "mixed" (chunk spans both)


def chunk_pages(
    pages: list[tuple[int, str, str]], chunk_words: int = 400, overlap_words: int = 60
) -> list[Chunk]:
    """pages is (page_number, text, extraction_method) in reading order.
    Builds a flat word stream tagged with source page + method, then slides
    a window with overlap across it -- so a chunk's page_start/page_end is
    the range of pages its words actually came from."""
    words: list[str] = []
    word_pages: list[int] = []
    word_methods: list[str] = []
    for page_number, text, method in pages:
        for word in text.split():
            words.append(word)
            word_pages.append(page_number)
            word_methods.append(method)

    if not words:
        return []

    step = max(1, chunk_words - overlap_words)
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        methods = set(word_methods[start:end])
        chunks.append(
            Chunk(
                text=" ".join(words[start:end]),
                page_start=word_pages[start],
                page_end=word_pages[end - 1],
                extraction_method=methods.pop() if len(methods) == 1 else "mixed",
            )
        )
        if end == len(words):
            break
        start += step
    return chunks
