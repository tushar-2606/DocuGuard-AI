from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Deadline, Document, Rule, Task, User
from app.models.schemas import DeadlineItem, RuleItem, TaskItem, TaskToggleResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api", tags=["Tasks, Deadlines & Rules"])


# --------------------------------------------------
# Tasks
# --------------------------------------------------

@router.get("/tasks", response_model=List[TaskItem])
def list_tasks(
    status_filter: Optional[str] = Query(None, description="all, pending, or completed"),
    priority: Optional[str] = Query(None, description="HIGH, MEDIUM, or LOW"),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Task, Document.filename)
        .join(Document, Task.document_id == Document.id)
        .filter(Task.user_id == current_user.id)
    )

    if status_filter == "pending":
        query = query.filter(Task.is_completed == False)  # noqa: E712
    elif status_filter == "completed":
        query = query.filter(Task.is_completed == True)  # noqa: E712

    if priority:
        query = query.filter(Task.priority == priority.upper())

    if category and category != "ALL":
        query = query.filter(Task.category == category)

    results = query.order_by(Task.id.desc()).all()

    items = []
    for t, doc_name in results:
        items.append(
            TaskItem(
                id=t.id,
                document_id=t.document_id,
                document_name=doc_name,
                task=t.task_text,
                deadline=t.deadline or "",
                priority=t.priority,
                category=t.category,
                confidence=t.confidence,
                is_completed=t.is_completed,
                detection_reason=t.detection_reason,
                source_snippet=t.source_snippet,
            )
        )
    return items


@router.patch("/tasks/{task_id}/toggle", response_model=TaskToggleResponse)
def toggle_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    task.is_completed = not task.is_completed
    db.commit()
    return TaskToggleResponse(id=task.id, is_completed=task.is_completed)


# --------------------------------------------------
# Deadlines
# --------------------------------------------------

@router.get("/deadlines", response_model=List[DeadlineItem])
def list_deadlines(
    status_filter: Optional[str] = Query(None, description="all, upcoming, or overdue"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = (
        db.query(Deadline, Document.filename)
        .join(Document, Deadline.document_id == Document.id)
        .filter(Deadline.user_id == current_user.id)
        .order_by(Deadline.deadline_date.asc())
        .all()
    )

    today_str = date.today().isoformat()
    items = []

    for dl, doc_name in results:
        is_overdue = bool(dl.deadline_date and dl.deadline_date < today_str and not dl.is_completed)

        if status_filter == "upcoming" and (is_overdue or dl.is_completed):
            continue
        if status_filter == "overdue" and not is_overdue:
            continue

        items.append(
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
    return items


@router.patch("/deadlines/{deadline_id}/toggle", response_model=TaskToggleResponse)
def toggle_deadline(
    deadline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dl = (
        db.query(Deadline)
        .filter(Deadline.id == deadline_id, Deadline.user_id == current_user.id)
        .first()
    )
    if not dl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deadline not found.",
        )

    dl.is_completed = not dl.is_completed
    db.commit()
    return TaskToggleResponse(id=dl.id, is_completed=dl.is_completed)


# --------------------------------------------------
# Rules
# --------------------------------------------------

@router.get("/rules", response_model=List[RuleItem])
def list_rules(
    rule_type: Optional[str] = Query(None, description="MANDATORY, PROHIBITED, or RECOMMENDED"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Rule, Document.filename)
        .join(Document, Rule.document_id == Document.id)
        .filter(Rule.user_id == current_user.id)
    )

    if rule_type and rule_type.upper() != "ALL":
        query = query.filter(Rule.rule_type == rule_type.upper())

    results = query.order_by(Rule.id.desc()).all()

    items = []
    for r, doc_name in results:
        items.append(
            RuleItem(
                id=r.id,
                document_id=r.document_id,
                document_name=doc_name,
                rule=r.rule_text,
                rule_type=r.rule_type,
                category=r.category,
                confidence=r.confidence,
                detection_reason=r.detection_reason,
                source_snippet=r.source_snippet,
            )
        )
    return items
