from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
from app.services.ai_service import analyze_document

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
            detail="Only PDF files are supported."
        )

    try:
        file_bytes = await file.read()

        pdf_document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        extracted_text = ""

        for page_number, page in enumerate(pdf_document):
            page_text = page.get_text()

            extracted_text += (
                f"\n--- Page {page_number + 1} ---\n"
                f"{page_text}"
            )

        page_count = len(pdf_document)

        pdf_document.close()

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found in this PDF."
            )

        # AI ANALYSIS
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

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {str(error)}"
        )