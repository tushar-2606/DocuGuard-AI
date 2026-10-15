from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.config import UPLOAD_RATE_LIMIT_PER_MINUTE
from app.database import get_db
from app.models.db_models import Deadline, Document, Rule, Task, User
from app.models.schemas import (
    DocumentDetailResponse,
    DocumentSummaryItem,
    ExtractedDeadline,
    ExtractedRule,
    ExtractedTask,
    DocumentAnalysis,
)
from app.services.ai_service import analyze_document
from app.services.auth_service import get_current_user, get_current_user_optional
from app.services.pdf_service import (
    MAX_UPLOAD_BYTES,
    content_sha256,
    extract_pdf_content,
    looks_like_pdf,
    sanitize_filename,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _lock_user_uploads(db: Session, user_id: int) -> None:
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
        return

    db.query(User.id).filter(User.id == user_id).with_for_update().one()


def _document_analysis(doc: Document) -> DocumentAnalysis:
    tasks_out = [
        ExtractedTask(
            id=t.id,
            task=t.task_text,
            description=getattr(t, "description", "") or "",
            deadline=t.deadline or "",
            deadline_time=getattr(t, "deadline_time", "") or "",
            priority=t.priority,
            category=t.category,
            confidence=t.confidence,
            is_completed=t.is_completed,
            detection_reason=t.detection_reason,
            source_snippet=t.source_snippet,
            page_number=getattr(t, "page_number", None),
            date_explicit=bool(getattr(t, "date_explicit", False)),
            review_status=getattr(t, "review_status", None) or "pending",
            extraction_method=getattr(t, "extraction_method", None) or "rule_based",
        )
        for t in doc.tasks
    ]
    rules_out = [
        ExtractedRule(
            id=r.id,
            rule=r.rule_text,
            rule_type=r.rule_type,
            category=r.category,
            confidence=r.confidence,
            detection_reason=r.detection_reason,
            source_snippet=r.source_snippet,
            page_number=getattr(r, "page_number", None),
        )
        for r in doc.rules
    ]
    deadlines_out = [
        ExtractedDeadline(
            id=dl.id,
            deadline_date=dl.deadline_date,
            deadline_time=getattr(dl, "deadline_time", "") or "",
            description=dl.description,
            is_completed=dl.is_completed,
            confidence=dl.confidence,
            detection_reason=dl.detection_reason,
            source_snippet=dl.source_snippet,
            page_number=getattr(dl, "page_number", None),
            date_explicit=bool(getattr(dl, "date_explicit", False)),
        )
        for dl in doc.deadlines
    ]
    warning_text = getattr(doc, "extraction_warnings", "") or ""

    return DocumentAnalysis(
        document_type=doc.document_type,
        summary=doc.summary,
        tasks=tasks_out,
        rules=rules_out,
        deadlines=deadlines_out,
        warnings=[warning for warning in warning_text.split("\n") if warning.strip()],
    )


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    check_rate_limit(request, "upload", UPLOAD_RATE_LIMIT_PER_MINUTE)

    safe_name = sanitize_filename(file.filename)

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The PDF exceeds the upload size limit.",
        )

    if not looks_like_pdf(file_bytes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only valid PDF files are supported.",
        )

    extracted_text, page_count, pdf_warnings = extract_pdf_content(file_bytes)
    file_hash = content_sha256(file_bytes)

    try:
        analysis = analyze_document(extracted_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    all_warnings = list(pdf_warnings) + list(analysis.warnings or [])
    analysis.warnings = all_warnings
    saved_doc_id = None

    if current_user:
        try:
            _lock_user_uploads(db, current_user.id)
            existing_doc = (
                db.query(Document)
                .options(
                    joinedload(Document.tasks),
                    joinedload(Document.rules),
                    joinedload(Document.deadlines),
                )
                .filter(
                    Document.user_id == current_user.id,
                    Document.content_hash == file_hash,
                )
                .order_by(Document.id.asc())
                .first()
            )
            if existing_doc:
                existing_analysis = _document_analysis(existing_doc)
                return {
                    "success": True,
                    "document_id": existing_doc.id,
                    "filename": existing_doc.filename,
                    "pages": existing_doc.pages,
                    "text_length": existing_doc.text_length,
                    "is_saved": True,
                    "content_hash": existing_doc.content_hash,
                    "warnings": existing_analysis.warnings,
                    "analysis": existing_analysis.model_dump(),
                }

            new_doc = Document(
                user_id=current_user.id,
                filename=safe_name,
                safe_filename=safe_name,
                document_type=analysis.document_type,
                pages=page_count,
                text_length=len(extracted_text),
                summary=analysis.summary,
                status="completed",
                processing_error="",
                content_hash=file_hash,
                extraction_warnings="\n".join(all_warnings),
            )
            db.add(new_doc)
            db.flush()
            saved_doc_id = new_doc.id

            saved_tasks = []
            for t in analysis.tasks:
                task_row = Task(
                    document_id=new_doc.id,
                    user_id=current_user.id,
                    task_text=t.task,
                    description=t.description or "",
                    deadline=t.deadline or "",
                    deadline_time=t.deadline_time or "",
                    priority=t.priority,
                    category=t.category,
                    confidence=t.confidence,
                    is_completed=False,
                    detection_reason=t.detection_reason,
                    source_snippet=t.source_snippet,
                    page_number=t.page_number,
                    date_explicit=t.date_explicit,
                    review_status=t.review_status or "pending",
                    extraction_method=t.extraction_method or "rule_based",
                )
                db.add(task_row)
                saved_tasks.append((t, task_row))

            saved_rules = []
            for r in analysis.rules:
                rule_row = Rule(
                    document_id=new_doc.id,
                    user_id=current_user.id,
                    rule_text=r.rule,
                    rule_type=r.rule_type,
                    category=r.category,
                    confidence=r.confidence,
                    detection_reason=r.detection_reason,
                    source_snippet=r.source_snippet,
                    page_number=r.page_number,
                )
                db.add(rule_row)
                saved_rules.append((r, rule_row))

            saved_deadlines = []
            for d in analysis.deadlines:
                dl_row = Deadline(
                    document_id=new_doc.id,
                    user_id=current_user.id,
                    deadline_date=d.deadline_date,
                    deadline_time=d.deadline_time or "",
                    description=d.description,
                    is_completed=False,
                    confidence=d.confidence,
                    detection_reason=d.detection_reason,
                    source_snippet=d.source_snippet,
                    page_number=d.page_number,
                    date_explicit=d.date_explicit,
                )
                db.add(dl_row)
                saved_deadlines.append((d, dl_row))

            db.commit()
            db.refresh(new_doc)

            for orig, row in saved_tasks:
                orig.id = row.id
            for orig, row in saved_rules:
                orig.id = row.id
            for orig, row in saved_deadlines:
                orig.id = row.id
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document analysis succeeded but saving failed. Please try again.",
            )

    return {
        "success": True,
        "document_id": saved_doc_id,
        "filename": safe_name,
        "pages": page_count,
        "text_length": len(extracted_text),
        "is_saved": bool(current_user),
        "content_hash": file_hash if current_user else None,
        "warnings": all_warnings,
        "analysis": analysis.model_dump(),
    }


@router.get("", response_model=List[DocumentSummaryItem])
def list_documents(
    search: Optional[str] = Query(None, description="Search by document name"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Document)
        .options(joinedload(Document.tasks), joinedload(Document.rules), joinedload(Document.deadlines))
        .filter(Document.user_id == current_user.id)
    )

    if search:
        escaped = _escape_like(search.strip().lower())
        query = query.filter(Document.filename.ilike(f"%{escaped}%", escape="\\"))

    if doc_type:
        query = query.filter(Document.document_type == doc_type)

    docs = query.order_by(Document.upload_timestamp.desc()).all()

    summary_list = []
    for d in docs:
        total_tasks = len(d.tasks)
        completed_tasks = sum(1 for t in d.tasks if t.is_completed)
        summary_list.append(
            DocumentSummaryItem(
                id=d.id,
                filename=d.filename,
                document_type=d.document_type,
                pages=d.pages,
                upload_timestamp=d.upload_timestamp,
                summary=d.summary,
                status=getattr(d, "status", None) or "completed",
                task_count=total_tasks,
                completed_task_count=completed_tasks,
                rule_count=len(d.rules),
                deadline_count=len(d.deadlines),
            )
        )

    return summary_list


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(Document)
        .options(joinedload(Document.tasks), joinedload(Document.rules), joinedload(Document.deadlines))
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    analysis = _document_analysis(doc)
    warning_text = getattr(doc, "extraction_warnings", "") or ""

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        pages=doc.pages,
        text_length=doc.text_length,
        summary=doc.summary,
        status=getattr(doc, "status", None) or "completed",
        processing_error=getattr(doc, "processing_error", "") or "",
        extraction_warnings=warning_text,
        upload_timestamp=doc.upload_timestamp,
        analysis=analysis,
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    filename = doc.filename
    db.delete(doc)
    db.commit()

    return {
        "success": True,
        "message": f"Document '{filename}' deleted successfully.",
    }
