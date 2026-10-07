from typing import Tuple
from fastapi import HTTPException
import fitz  # PyMuPDF

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 100


def extract_pdf_content(file_bytes: bytes) -> Tuple[str, int]:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF file is empty.")

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The PDF exceeds the 15 MB upload limit.",
        )

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf_document:
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

            extracted_text = "\n".join(
                f"--- Page {page_number + 1} ---\n{page.get_text()}"
                for page_number, page in enumerate(pdf_document)
            )

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text was found. Scanned PDFs without selectable text are not supported yet.",
            )

        return extracted_text, page_count

    except (fitz.FileDataError, fitz.EmptyFileError):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid or readable PDF.",
        )
