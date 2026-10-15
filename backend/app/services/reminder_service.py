import logging
import smtplib
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import update
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.database import SessionLocal
from app.models.db_models import (
    Deadline,
    Document,
    Notification,
    ReminderPreference,
    Task,
    User,
)

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

def get_or_create_preferences(db: Session, user_id: int) -> ReminderPreference:
    preferences = (
        db.query(ReminderPreference)
        .filter(ReminderPreference.user_id == user_id)
        .first()
    )
    if preferences:
        return preferences
    preferences = ReminderPreference(
        user_id=user_id,
        timezone=config.APP_TIMEZONE,
        date_only_time=config.DEFAULT_DATE_ONLY_REMINDER_TIME,
    )
    db.add(preferences)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        preferences = (
            db.query(ReminderPreference)
            .filter(ReminderPreference.user_id == user_id)
            .first()
        )
        if not preferences:
            raise
    db.refresh(preferences)
    return preferences


def smtp_is_configured() -> bool:
    return config.SMTP_CONFIGURED


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _deadline_datetime(
    date_value: str,
    time_value: str,
    date_only_time: str,
    timezone_name: str,
) -> datetime | None:
    try:
        deadline_date = date.fromisoformat((date_value or "").strip())
        selected_time = time.fromisoformat(
            (time_value or date_only_time).strip()
        )
        tz = ZoneInfo(timezone_name)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        logger.warning("Skipping reminder with invalid date, time, or timezone.")
        return None
    return datetime.combine(deadline_date, selected_time, tzinfo=tz)


def _stage_due(
    due_at: datetime,
    now: datetime,
    timezone_name: str,
    preferences: ReminderPreference | None,
) -> str | None:
    local_due = due_at.astimezone(ZoneInfo(timezone_name))
    local_now = now.astimezone(ZoneInfo(timezone_name))

    if local_now > local_due:
        if preferences and preferences.remind_overdue:
            return "overdue"
        grace = max(120, config.REMINDER_CHECK_INTERVAL_SECONDS * 2)
        if (
            preferences is None
            or preferences.remind_at_deadline
        ) and local_now - local_due <= timedelta(seconds=grace):
            return "at_deadline"
        return None

    stages = []
    if preferences is None or preferences.remind_three_days:
        stages.append(("three_days", local_due - timedelta(days=3)))
    if preferences is None or preferences.remind_one_day:
        stages.append(("one_day", local_due - timedelta(days=1)))
    if preferences is None or preferences.remind_at_deadline:
        stages.append(("at_deadline", local_due))

    due_stages = [
        (scheduled_at, name)
        for name, scheduled_at in stages
        if scheduled_at <= local_now
    ]
    if not due_stages:
        return None
    return max(due_stages, key=lambda item: item[0])[1]


def _notification_for_target(
    *,
    user_id: int,
    document_id: int,
    target_type: str,
    target_id: int,
    title_text: str,
    date_value: str,
    time_value: str,
    timezone_name: str,
    preferences: ReminderPreference | None,
    now: datetime,
) -> Notification | None:
    due_at = _deadline_datetime(
        date_value,
        time_value,
        preferences.date_only_time
        if preferences
        else config.DEFAULT_DATE_ONLY_REMINDER_TIME,
        timezone_name,
    )
    if due_at is None:
        return None

    stage = _stage_due(due_at, now, timezone_name, preferences)
    if stage is None:
        return None

    target_key = f"{target_type}:{target_id}"
    readable_stage = {
        "three_days": "in 3 days",
        "one_day": "tomorrow",
        "at_deadline": "now",
        "overdue": "overdue",
    }[stage]
    title = f"Deadline reminder: {title_text.strip()}"[:255]
    time_suffix = f" at {time_value}" if time_value else ""
    message = (
        f"This item is due {date_value}{time_suffix} ({timezone_name}) "
        f"and is {readable_stage}."
    )
    if preferences and preferences.email_enabled:
        email_status = "pending" if smtp_is_configured() else "not_configured"
    else:
        email_status = "disabled"

    return Notification(
        user_id=user_id,
        document_id=document_id,
        task_id=target_id if target_type == "task" else None,
        deadline_id=target_id if target_type == "deadline" else None,
        target_key=target_key,
        reminder_key=f"{target_key}:{stage}:{date_value}",
        title=title,
        message=message,
        stage=stage,
        reminder_date=date_value,
        deadline_at=_utc(due_at).replace(tzinfo=None),
        email_status=email_status,
    )


def process_due_reminders(
    now: datetime | None = None,
    db: Session | None = None,
) -> int:
    """Persist one idempotent reminder per due stage and deliver opted-in email."""
    owns_session = db is None
    session = db or SessionLocal()
    current_time = _utc(now or datetime.now(timezone.utc))
    created_ids: list[int] = []
    try:
        users = session.query(User).filter(User.is_active == True).all()  # noqa: E712
        for user in users:
            preferences = (
                session.query(ReminderPreference)
                .filter(ReminderPreference.user_id == user.id)
                .first()
            )
            if preferences and not preferences.enabled:
                continue
            timezone_name = (
                preferences.timezone if preferences else config.APP_TIMEZONE
            )
            try:
                ZoneInfo(timezone_name)
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning(
                    "Skipping reminders for user %s with an invalid timezone.",
                    user.id,
                )
                continue

            tasks = (
                session.query(Task, Document.filename)
                .join(Document, Task.document_id == Document.id)
                .filter(
                    Task.user_id == user.id,
                    Document.user_id == user.id,
                    Task.is_completed == False,  # noqa: E712
                    Task.deadline.isnot(None),
                    Task.deadline != "",
                )
                .all()
            )
            task_dates_by_document: set[tuple[int, str]] = set()
            candidates: list[Notification] = []
            for task, _document_name in tasks:
                task_dates_by_document.add((task.document_id, task.deadline))
                candidate = _notification_for_target(
                    user_id=user.id,
                    document_id=task.document_id,
                    target_type="task",
                    target_id=task.id,
                    title_text=task.task_text,
                    date_value=task.deadline,
                    time_value=task.deadline_time or "",
                    timezone_name=timezone_name,
                    preferences=preferences,
                    now=current_time,
                )
                if candidate:
                    candidates.append(candidate)

            deadlines = (
                session.query(Deadline)
                .join(Document, Deadline.document_id == Document.id)
                .filter(
                    Deadline.user_id == user.id,
                    Document.user_id == user.id,
                    Deadline.is_completed == False,  # noqa: E712
                )
                .all()
            )
            for deadline in deadlines:
                if (
                    deadline.document_id,
                    deadline.deadline_date,
                ) in task_dates_by_document:
                    continue
                candidate = _notification_for_target(
                    user_id=user.id,
                    document_id=deadline.document_id,
                    target_type="deadline",
                    target_id=deadline.id,
                    title_text=deadline.description,
                    date_value=deadline.deadline_date,
                    time_value=deadline.deadline_time or "",
                    timezone_name=timezone_name,
                    preferences=preferences,
                    now=current_time,
                )
                if candidate:
                    candidates.append(candidate)

            for candidate in candidates:
                try:
                    with session.begin_nested():
                        session.add(candidate)
                        session.flush()
                    created_ids.append(candidate.id)
                except IntegrityError:
                    logger.debug("Reminder already exists: %s", candidate.target_key)
        session.commit()
        for notification_id in created_ids:
            _deliver_pending_email(notification_id)
        pending_email_ids = [
            row[0]
            for row in session.query(Notification.id)
            .filter(Notification.email_status == "pending")
            .all()
        ]
        for notification_id in pending_email_ids:
            _deliver_pending_email(notification_id)
        return len(created_ids)
    except Exception:
        session.rollback()
        logger.exception("Reminder processing failed.")
        raise
    finally:
        if owns_session:
            session.close()


def _deliver_pending_email(notification_id: int) -> None:
    session = SessionLocal()
    try:
        notification = (
            session.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.email_status == "pending",
            )
            .first()
        )
        if not notification:
            return
        preferences = (
            session.query(ReminderPreference)
            .filter(ReminderPreference.user_id == notification.user_id)
            .first()
        )
        user = session.query(User).filter(User.id == notification.user_id).first()
        if (
            not smtp_is_configured()
            or not preferences
            or not preferences.enabled
            or not preferences.email_enabled
            or not user
        ):
            notification.email_status = (
                "not_configured" if not smtp_is_configured() else "disabled"
            )
            session.commit()
            return

        claimed = session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.email_status == "pending",
            )
            .values(
                email_status="sending",
                email_attempts=Notification.email_attempts + 1,
            )
        )
        if not claimed.rowcount:
            session.rollback()
            return
        session.commit()
        notification = (
            session.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )
        if not notification:
            return

        message = EmailMessage()
        message["Subject"] = notification.title
        message["From"] = config.SMTP_FROM
        message["To"] = user.email
        message.set_content(notification.message)

        if config.SMTP_USE_SSL:
            client = smtplib.SMTP_SSL(
                config.SMTP_HOST, config.SMTP_PORT, timeout=15
            )
        else:
            client = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        with client:
            if config.SMTP_USE_TLS:
                client.starttls()
            if config.SMTP_USERNAME:
                client.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            client.send_message(message)

        notification.email_status = "sent"
        notification.email_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        notification.email_last_error = ""
        session.commit()
    except Exception as exc:
        session.rollback()
        failed = (
            session.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )
        if failed:
            failed.email_status = "failed"
            failed.email_last_error = str(exc)[:500]
            session.commit()
        logger.warning(
            "Email delivery failed for notification %s (%s).",
            notification_id,
            type(exc).__name__,
        )
    finally:
        session.close()


def start_reminder_scheduler() -> None:
    global _scheduler
    if not config.ENABLE_REMINDER_SCHEDULER:
        logger.info("Reminder scheduler disabled by configuration.")
        return
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        process_due_reminders,
        "interval",
        seconds=config.REMINDER_CHECK_INTERVAL_SECONDS,
        next_run_time=datetime.now(timezone.utc),
        id="docuguard-reminder-check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=config.REMINDER_CHECK_INTERVAL_SECONDS * 2,
    )
    _scheduler.start()
    logger.info(
        "Reminder scheduler started (interval=%s seconds).",
        config.REMINDER_CHECK_INTERVAL_SECONDS,
    )


def shutdown_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
