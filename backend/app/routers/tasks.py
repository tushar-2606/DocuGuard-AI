from datetime import date, datetime
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Deadline, Document, Rule, Task, User
from app.models.schemas import (
    DeadlineItem,
    RuleItem,
    TaskItem,
    TaskToggleResponse,
    TaskUpdateRequest,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api", tags=["Tasks, Deadlines & Rules"])


def _task_to_item(t: Task, doc_name: str) -> TaskItem:
    return TaskItem(
        id=t.id,
        document_id=t.document_id,
        document_name=doc_name,
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


@router.get("/tasks", response_model=List[TaskItem])
def list_tasks(
    status_filter: Optional[str] = Query(None, description="all, pending, completed, overdue, undated"),
    priority: Optional[str] = Query(None, description="HIGH, MEDIUM, or LOW"),
    category: Optional[str] = Query(None),
    document_id: Optional[int] = Query(None),
    review_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("created_desc", description="due_asc, due_desc, priority, created_desc"),
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

    if document_id is not None:
        query = query.filter(Task.document_id == document_id)

    if review_status:
        query = query.filter(Task.review_status == review_status)

    if search:
        like = f"%{search.strip()}%"
        query = query.filter(Task.task_text.ilike(like))

    results = query.all()
    today_str = date.today().isoformat()

    items = []
    for t, doc_name in results:
        deadline = t.deadline or ""
        if status_filter == "overdue":
            if not (deadline and deadline < today_str and not t.is_completed):
                continue
        elif status_filter == "undated":
            if deadline:
                continue
        items.append(_task_to_item(t, doc_name))

    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    if sort == "due_asc":
        items.sort(key=lambda x: (x.deadline == "", x.deadline or "9999"))
    elif sort == "due_desc":
        items.sort(key=lambda x: (x.deadline == "", x.deadline or ""), reverse=True)
    elif sort == "priority":
        items.sort(key=lambda x: priority_rank.get(x.priority, 9))
    else:
        items.sort(key=lambda x: x.id, reverse=True)

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
    task.updated_at = datetime.utcnow()
    db.commit()
    return TaskToggleResponse(id=task.id, is_completed=task.is_completed)


@router.patch("/tasks/{task_id}", response_model=TaskItem)
def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
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

    data = payload.model_dump(exclude_unset=True)
    if "task" in data and data["task"] is not None:
        task.task_text = data["task"].strip()
    if "description" in data and data["description"] is not None:
        task.description = data["description"]
    if "deadline" in data and data["deadline"] is not None:
        deadline = data["deadline"].strip()
        if deadline and not _looks_like_iso_date(deadline):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deadline must be YYYY-MM-DD or empty.",
            )
        task.deadline = deadline
        if deadline:
            task.date_explicit = True
        else:
            task.deadline_time = ""
    if "deadline_time" in data and data["deadline_time"] is not None:
        deadline_time = data["deadline_time"].strip()
        if deadline_time and not (data.get("deadline", task.deadline) or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A deadline time requires a calendar date.",
            )
        task.deadline_time = deadline_time
    if "priority" in data and data["priority"] is not None:
        task.priority = data["priority"]
    if "category" in data and data["category"] is not None:
        task.category = data["category"].strip() or "General"
    if "review_status" in data and data["review_status"] is not None:
        task.review_status = data["review_status"]
        if data["review_status"] == "rejected":
            task.is_completed = True
    if "is_completed" in data and data["is_completed"] is not None:
        task.is_completed = data["is_completed"]

    task.updated_at = datetime.utcnow()
    db.commit()

    doc = db.query(Document).filter(Document.id == task.document_id).first()
    return _task_to_item(task, doc.filename if doc else "")


@router.delete("/tasks/{task_id}")
def delete_task(
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
    db.delete(task)
    db.commit()
    return {"success": True, "message": "Task deleted."}


def _looks_like_iso_date(value: str) -> bool:
    if value == "":
        return True
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


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
                deadline_time=getattr(dl, "deadline_time", "") or "",
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
                page_number=getattr(r, "page_number", None),
            )
        )
    return items
