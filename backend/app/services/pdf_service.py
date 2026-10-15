import hashlib
import re
from pathlib import Path
from typing import List, Tuple

from fastapi import HTTPException
import fitz  # PyMuPDF

from app.config import MAX_PDF_PAGES, MAX_UPLOAD_BYTES

# PDF files begin with "%PDF-"
PDF_MAGIC = b"%PDF-"


def looks_like_pdf(file_bytes: bytes) -> bool:
    if not file_bytes or len(file_bytes) < 5:
        return False
    # Allow optional leading whitespace/BOM before magic
    head = file_bytes[:1024].lstrip()
    return head.startswith(PDF_MAGIC)


def sanitize_filename(filename: str | None) -> str:
    raw = (filename or "uploaded_document.pdf").strip()
    name = Path(raw).name  # drop any path components
    name = re.sub(r"[^\w.\- ()\[\]]+", "_", name)
    name = name.strip(" ._")
    if not name.lower().endswith(".pdf"):
        name = f"{name or 'document'}.pdf"
    return name[:200]


def content_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def extract_pdf_content(file_bytes: bytes) -> Tuple[str, int, List[str]]:
    """
    Returns (full_text_with_page_markers, page_count, warnings).
    """
    warnings: List[str] = []

    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF file is empty.")

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The PDF exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )

    if not looks_like_pdf(file_bytes):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid PDF.",
        )

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf_document:
            if pdf_document.is_encrypted:
                # Try empty password; otherwise fail clearly
                if not pdf_document.authenticate(""):
                    raise HTTPException(
                        status_code=400,
                        detail="This PDF is password-protected and cannot be processed.",
                    )

            page_count = len(pdf_document)
            if page_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded PDF contains no pages.",
                )
            if page_count > MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=413,
                    detail=f"The PDF exceeds the {MAX_PDF_PAGES}-page limit.",
                )

            page_texts: List[str] = []
            empty_pages = 0
            for page_number, page in enumerate(pdf_document):
                text = page.get_text() or ""
                if not text.strip():
                    empty_pages += 1
                page_texts.append(f"--- Page {page_number + 1} ---\n{text}")

            extracted_text = "\n".join(page_texts)

            if empty_pages == page_count:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No readable text was found. This appears to be a scanned or "
                        "image-only PDF. Optical character recognition (OCR) is not "
                        "enabled in this build — please upload a PDF with selectable text."
                    ),
                )

            if empty_pages > 0:
                warnings.append(
                    f"{empty_pages} of {page_count} page(s) contained no extractable text "
                    "(possible scanned pages). OCR is not enabled."
                )

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text was found. Scanned PDFs without selectable text "
                    "are not supported without OCR."
                ),
            )

        return extracted_text, page_count, warnings

    except HTTPException:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid or readable PDF.",
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="The PDF could not be processed. It may be corrupted or unsupported.",
        )
