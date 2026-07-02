"""Per-page PDF text extraction: native text layer where available, OCR
fallback for scanned pages. The only module that talks to PyMuPDF/Tesseract."""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

NATIVE_TEXT_MIN_CHARS = 20  # below this, a page is treated as scanned and OCR'd
OCR_PROGRESS_EVERY = 50
TESSERACT_FALLBACK_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_tesseract_ready = False


def _ensure_tesseract():
    global _tesseract_ready
    if _tesseract_ready:
        return
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_FALLBACK_CMD
    _tesseract_ready = True


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    method: str  # "native" or "ocr"


def _ocr_image(png_bytes: bytes) -> str:
    _ensure_tesseract()
    image = Image.open(io.BytesIO(png_bytes))
    return pytesseract.image_to_string(image)


def extract_pages(pdf_path: Path, ocr_dpi: int = 200, workers: int = 1, log=print) -> list[PageText]:
    """Extracts text for every page of pdf_path. PyMuPDF access (opening the
    doc, reading native text, rendering scanned pages to images) all happens
    on this thread -- MuPDF documents aren't safe to share across threads.
    Only the OCR calls themselves (external tesseract subprocesses, which
    release the GIL while running) are farmed out to a thread pool."""
    doc = fitz.open(pdf_path)
    try:
        page_count = len(doc)
        results: dict[int, PageText] = {}
        ocr_jobs: list[tuple[int, bytes]] = []

        for i in range(page_count):
            page = doc[i]
            native = page.get_text()
            if len(native.strip()) >= NATIVE_TEXT_MIN_CHARS:
                results[i + 1] = PageText(i + 1, native, "native")
            else:
                pix = page.get_pixmap(dpi=ocr_dpi)
                ocr_jobs.append((i + 1, pix.tobytes("png")))

        if not ocr_jobs:
            return [results[n] for n in sorted(results)]

        log(f"[pipeline] {pdf_path.name}: {len(ocr_jobs)}/{page_count} pages need OCR")
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(_ocr_image, png): page_number for page_number, png in ocr_jobs}
            for future in as_completed(futures):
                page_number = futures[future]
                results[page_number] = PageText(page_number, future.result(), "ocr")
                done += 1
                if done % OCR_PROGRESS_EVERY == 0 or done == len(ocr_jobs):
                    log(f"[pipeline] {pdf_path.name}: OCR {done}/{len(ocr_jobs)} pages")

        return [results[n] for n in sorted(results)]
    finally:
        doc.close()
