from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

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
from app.services.pdf_service import MAX_UPLOAD_BYTES, extract_pdf_content

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf" and not (
        file.filename and file.filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    extracted_text, page_count = extract_pdf_content(file_bytes)

    analysis = analyze_document(extracted_text)
    saved_doc_id = None

    if current_user:
        new_doc = Document(
            user_id=current_user.id,
            filename=file.filename or "uploaded_document.pdf",
            document_type=analysis.document_type,
            pages=page_count,
            text_length=len(extracted_text),
            summary=analysis.summary,
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        saved_doc_id = new_doc.id

        # Persist tasks
        saved_tasks = []
        for t in analysis.tasks:
            task_row = Task(
                document_id=new_doc.id,
                user_id=current_user.id,
                task_text=t.task,
                deadline=t.deadline or "",
                priority=t.priority,
                category=t.category,
                confidence=t.confidence,
                is_completed=False,
                detection_reason=t.detection_reason,
                source_snippet=t.source_snippet,
            )
            db.add(task_row)
            saved_tasks.append((t, task_row))

        # Persist rules
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
            )
            db.add(rule_row)
            saved_rules.append((r, rule_row))

        # Persist deadlines
        saved_deadlines = []
        for d in analysis.deadlines:
            dl_row = Deadline(
                document_id=new_doc.id,
                user_id=current_user.id,
                deadline_date=d.deadline_date,
                description=d.description,
                is_completed=False,
                confidence=d.confidence,
                detection_reason=d.detection_reason,
                source_snippet=d.source_snippet,
            )
            db.add(dl_row)
            saved_deadlines.append((d, dl_row))

        db.commit()

        # Update IDs in response
        for orig, row in saved_tasks:
            orig.id = row.id
        for orig, row in saved_rules:
            orig.id = row.id
        for orig, row in saved_deadlines:
            orig.id = row.id

    return {
        "success": True,
        "document_id": saved_doc_id,
        "filename": file.filename,
        "pages": page_count,
        "text_length": len(extracted_text),
        "is_saved": bool(current_user),
        "analysis": analysis.model_dump(),
    }


@router.get("", response_model=List[DocumentSummaryItem])
def list_documents(
    search: Optional[str] = Query(None, description="Search by document name"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)

    if search:
        search_filter = f"%{search.strip().lower()}%"
        query = query.filter(Document.filename.ilike(search_filter))

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
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    tasks_out = [
        ExtractedTask(
            id=t.id,
            task=t.task_text,
            deadline=t.deadline or "",
            priority=t.priority,
            category=t.category,
            confidence=t.confidence,
            is_completed=t.is_completed,
            detection_reason=t.detection_reason,
            source_snippet=t.source_snippet,
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
        )
        for r in doc.rules
    ]

    deadlines_out = [
        ExtractedDeadline(
            id=dl.id,
            deadline_date=dl.deadline_date,
            description=dl.description,
            is_completed=dl.is_completed,
            confidence=dl.confidence,
            detection_reason=dl.detection_reason,
            source_snippet=dl.source_snippet,
        )
        for dl in doc.deadlines
    ]

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        pages=doc.pages,
        text_length=doc.text_length,
        summary=doc.summary,
        upload_timestamp=doc.upload_timestamp,
        analysis=DocumentAnalysis(
            document_type=doc.document_type,
            summary=doc.summary,
            tasks=tasks_out,
            rules=rules_out,
            deadlines=deadlines_out,
        ),
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

    db.delete(doc)
    db.commit()

    return {
        "success": True,
        "message": f"Document '{doc.filename}' deleted successfully.",
    }
