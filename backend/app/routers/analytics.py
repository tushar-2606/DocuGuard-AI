from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Deadline, Document, Rule, Task, User
from app.models.schemas import (
    DashboardStats,
    DeadlineItem,
    DocumentSummaryItem,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.upload_timestamp.desc())
        .all()
    )
    total_docs = len(docs)

    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    pending_tasks = sum(1 for t in tasks if not t.is_completed)
    completed_tasks = sum(1 for t in tasks if t.is_completed)

    rules = db.query(Rule).filter(Rule.user_id == current_user.id).all()
    mandatory_rules = sum(1 for r in rules if r.rule_type == "MANDATORY")
    prohibited_rules = sum(1 for r in rules if r.rule_type == "PROHIBITED")
    recommended_rules = sum(1 for r in rules if r.rule_type == "RECOMMENDED")

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
        mandatory_rules=mandatory_rules,
        prohibited_rules=prohibited_rules,
        recommended_rules=recommended_rules,
        recent_documents=recent_summary,
        upcoming_deadline_items=upcoming_items,
    )
