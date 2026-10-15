from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.config import REMINDER_CHECK_INTERVAL_SECONDS
from app.database import get_db
from app.models.db_models import (
    Deadline,
    Document,
    Notification,
    ReminderPreference,
    Task,
    User,
)
from app.models.schemas import (
    NotificationItem,
    ReminderPreferenceItem,
    ReminderPreferenceUpdate,
)
from app.services.auth_service import get_current_user
from app.services.reminder_service import get_or_create_preferences, smtp_is_configured

router = APIRouter(prefix="/api", tags=["Notifications"])


def _preference_item(preferences: ReminderPreference) -> ReminderPreferenceItem:
    return ReminderPreferenceItem(
        enabled=preferences.enabled,
        desktop_enabled=preferences.desktop_enabled,
        email_enabled=preferences.email_enabled,
        remind_three_days=preferences.remind_three_days,
        remind_one_day=preferences.remind_one_day,
        remind_at_deadline=preferences.remind_at_deadline,
        remind_overdue=preferences.remind_overdue,
        date_only_time=preferences.date_only_time,
        timezone=preferences.timezone,
        email_configured=smtp_is_configured(),
        scheduler_interval_seconds=REMINDER_CHECK_INTERVAL_SECONDS,
    )


@router.get("/reminder-preferences", response_model=ReminderPreferenceItem)
def get_reminder_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _preference_item(get_or_create_preferences(db, current_user.id))


@router.patch("/reminder-preferences", response_model=ReminderPreferenceItem)
def update_reminder_preferences(
    payload: ReminderPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preferences = get_or_create_preferences(db, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(preferences, field, value)
    preferences.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(preferences)
    return _preference_item(preferences)


@router.get("/notifications", response_model=List[NotificationItem])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Notification, Document.filename)
        .join(Document, Notification.document_id == Document.id)
        .filter(
            Notification.user_id == current_user.id,
            Document.user_id == current_user.id,
        )
    )
    if unread_only:
        rows = rows.filter(Notification.is_read == False)  # noqa: E712
    rows = rows.order_by(Notification.created_at.desc()).limit(limit).all()

    items = []
    for notification, document_name in rows:
        task = (
            db.query(Task)
            .filter(
                Task.id == notification.task_id,
                Task.user_id == current_user.id,
                Task.document_id == notification.document_id,
            )
            .first()
            if notification.task_id
            else None
        )
        deadline = (
            db.query(Deadline)
            .filter(
                Deadline.id == notification.deadline_id,
                Deadline.user_id == current_user.id,
                Deadline.document_id == notification.document_id,
            )
            .first()
            if notification.deadline_id
            else None
        )
        items.append(
            NotificationItem(
                id=notification.id,
                title=notification.title,
                message=notification.message,
                stage=notification.stage,
                target_type="task" if task else "deadline",
                target_id=task.id if task else deadline.id,
                document_id=notification.document_id,
                document_name=document_name,
                deadline_date=(task.deadline if task else deadline.deadline_date) or "",
                deadline_time=(
                    (task.deadline_time if task else deadline.deadline_time) or ""
                ),
                is_read=notification.is_read,
                created_at=notification.created_at,
                email_status=notification.email_status,
                email_last_error=notification.email_last_error or "",
            )
        )
    return items


@router.get("/notifications/unread-count")
def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .scalar()
    )
    return {"unread_count": count or 0}


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.is_read = True
    db.commit()
    return {"success": True, "is_read": True}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    db.commit()
    return {"success": True, "updated_count": result.rowcount or 0}


@router.post("/notifications/{notification_id}/desktop-delivered")
def mark_desktop_notification_delivered(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preferences = (
        db.query(ReminderPreference)
        .filter(ReminderPreference.user_id == current_user.id)
        .first()
    )
    if not preferences or not preferences.desktop_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Desktop notifications are not enabled for this account.",
        )
    if not preferences.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reminders are disabled for this account.",
        )
    result = db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.desktop_notified_at.is_(None),
        )
        .values(
            desktop_notified_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
    )
    db.commit()
    if not result.rowcount:
        return {"success": True, "delivered": False}
    return {"success": True, "delivered": True}
