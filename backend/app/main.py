import logging

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
from app.services.ai_service import analyze_document

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 100

app = FastAPI(
    title="DocuGuard AI",
    description="AI-powered document intelligence and deadline extraction system",
    version="1.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "DocuGuard AI API is running",
        "status": "online",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DocuGuard AI Backend",
    }


# --------------------------------------------------
# PDF Text Extraction
# --------------------------------------------------

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    try:
        file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="The PDF exceeds the 15 MB upload limit.",
            )

        with fitz.open(stream=file_bytes, filetype="pdf") as pdf_document:
            page_count = len(pdf_document)
            if page_count > MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=413,
                    detail=f"The PDF exceeds the {MAX_PDF_PAGES}-page limit.",
                )
            if page_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded PDF contains no pages.",
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

        analysis = analyze_document(extracted_text)

        return {
            "success": True,
            "filename": file.filename,
            "pages": page_count,
            "text_length": len(extracted_text),
            "analysis": analysis.model_dump(),
        }

    except HTTPException:
        raise

    except (fitz.FileDataError, fitz.EmptyFileError):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid or readable PDF.",
        ) from None

    except Exception:
        logger.exception("Document processing failed")
        raise HTTPException(
            status_code=500,
            detail="Document processing failed. Please try another PDF.",
        ) from None