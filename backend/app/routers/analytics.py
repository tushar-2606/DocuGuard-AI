import csv
import io
from datetime import date
from collections import Counter

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.db_models import Deadline, Document, Rule, Task, User
from app.models.schemas import (
    DashboardStats,
    DeadlineItem,
    DocumentSummaryItem,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _sanitize_csv_cell(value) -> str:
    """Prefix dangerous spreadsheet formula characters to reduce CSV injection risk."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(Document)
        .options(joinedload(Document.tasks), joinedload(Document.rules), joinedload(Document.deadlines))
        .filter(Document.user_id == current_user.id)
        .order_by(Document.upload_timestamp.desc())
        .all()
    )
    total_docs = len(docs)
    documents_failed = sum(1 for d in docs if (getattr(d, "status", None) or "") == "failed")

    pending_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.user_id == current_user.id, Task.is_completed == False)  # noqa: E712
        .scalar()
        or 0
    )
    completed_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.user_id == current_user.id, Task.is_completed == True)  # noqa: E712
        .scalar()
        or 0
    )

    priority_rows = (
        db.query(Task.priority, func.count(Task.id))
        .filter(Task.user_id == current_user.id)
        .group_by(Task.priority)
        .all()
    )
    tasks_by_priority = {p or "LOW": c for p, c in priority_rows}

    category_rows = (
        db.query(Task.category, func.count(Task.id))
        .filter(Task.user_id == current_user.id)
        .group_by(Task.category)
        .all()
    )
    tasks_by_category = {c or "General": n for c, n in category_rows}

    rule_rows = (
        db.query(Rule.rule_type, func.count(Rule.id))
        .filter(Rule.user_id == current_user.id)
        .group_by(Rule.rule_type)
        .all()
    )
    rule_counts = Counter({r: n for r, n in rule_rows})

    deadlines = (
        db.query(Deadline, Document.filename)
        .join(Document, Deadline.document_id == Document.id)
        .filter(Deadline.user_id == current_user.id)
        .order_by(Deadline.deadline_date.asc())
        .all()
    )

    today_str = date.today().isoformat()
    upcoming_count = 0
    overdue_count = 0
    upcoming_items = []

    for dl, doc_name in deadlines:
        is_overdue = bool(dl.deadline_date and dl.deadline_date < today_str and not dl.is_completed)
        is_upcoming = bool(dl.deadline_date and dl.deadline_date >= today_str and not dl.is_completed)

        if is_overdue:
            overdue_count += 1
        elif is_upcoming:
            upcoming_count += 1

        if not dl.is_completed and len(upcoming_items) < 5:
            upcoming_items.append(
                DeadlineItem(
                    id=dl.id,
                    document_id=dl.document_id,
                    document_name=doc_name,
                    deadline_date=dl.deadline_date,
                    description=dl.description,
                    is_completed=dl.is_completed,
                    is_overdue=is_overdue,
                    confidence=dl.confidence,
                    detection_reason=dl.detection_reason,
                    source_snippet=dl.source_snippet,
                    page_number=getattr(dl, "page_number", None),
                    date_explicit=bool(getattr(dl, "date_explicit", False)),
                )
            )

    recent_summary = []
    for d in docs[:5]:
        total_d_tasks = len(d.tasks)
        comp_d_tasks = sum(1 for t in d.tasks if t.is_completed)
        recent_summary.append(
            DocumentSummaryItem(
                id=d.id,
                filename=d.filename,
                document_type=d.document_type,
                pages=d.pages,
                upload_timestamp=d.upload_timestamp,
                summary=d.summary,
                status=getattr(d, "status", None) or "completed",
                task_count=total_d_tasks,
                completed_task_count=comp_d_tasks,
                rule_count=len(d.rules),
                deadline_count=len(d.deadlines),
            )
        )

    return DashboardStats(
        total_documents=total_docs,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        upcoming_deadlines=upcoming_count,
        overdue_deadlines=overdue_count,
        mandatory_rules=rule_counts.get("MANDATORY", 0),
        prohibited_rules=rule_counts.get("PROHIBITED", 0),
        recommended_rules=rule_counts.get("RECOMMENDED", 0),
        tasks_by_priority=tasks_by_priority,
        tasks_by_category=tasks_by_category,
        documents_failed=documents_failed,
        recent_documents=recent_summary,
        upcoming_deadline_items=upcoming_items,
    )


@router.get("/export/tasks.csv")
def export_tasks_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Task, Document.filename)
        .join(Document, Task.document_id == Document.id)
        .filter(Task.user_id == current_user.id)
        .order_by(Task.id.asc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "document",
            "task",
            "deadline",
            "priority",
            "category",
            "completed",
            "review_status",
            "confidence_heuristic",
            "page_number",
            "date_explicit",
            "source_snippet",
        ]
    )
    for t, doc_name in rows:
        writer.writerow(
            [
                t.id,
                _sanitize_csv_cell(doc_name),
                _sanitize_csv_cell(t.task_text),
                _sanitize_csv_cell(t.deadline or ""),
                _sanitize_csv_cell(t.priority),
                _sanitize_csv_cell(t.category),
                "yes" if t.is_completed else "no",
                _sanitize_csv_cell(getattr(t, "review_status", "") or "pending"),
                t.confidence,
                getattr(t, "page_number", "") or "",
                "yes" if getattr(t, "date_explicit", False) else "no",
                _sanitize_csv_cell(t.source_snippet or ""),
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=docuguard_tasks.csv"},
    )
