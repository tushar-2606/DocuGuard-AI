from datetime import datetime, timezone

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
from app.services.reminder_service import process_due_reminders


def _user_document(db, email="reminders@example.com"):
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            full_name="Reminder User",
            hashed_password="test-hash",
            is_active=True,
        )
        db.add(user)
        db.flush()
    document = Document(
        user_id=user.id,
        filename="placement-notice.pdf",
        safe_filename="placement-notice.pdf",
        document_type="notice",
        summary="Placement dates",
    )
    db.add(document)
    db.flush()
    return user, document


def test_preferences_are_authenticated_validated_and_user_scoped(client, auth_headers):
    response = client.get("/api/reminder-preferences", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["timezone"] == "UTC"
    assert response.json()["date_only_time"] == "09:00"
    assert response.json()["email_configured"] is False

    response = client.patch(
        "/api/reminder-preferences",
        headers=auth_headers,
        json={
            "timezone": "Europe/London",
            "date_only_time": "08:30",
            "remind_overdue": True,
            "desktop_enabled": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/London"
    assert response.json()["date_only_time"] == "08:30"
    assert response.json()["remind_overdue"] is True

    response = client.patch(
        "/api/reminder-preferences",
        headers=auth_headers,
        json={"timezone": "Not/A_Timezone"},
    )
    assert response.status_code == 422


def test_reminder_api_marks_read_and_does_not_leak_to_other_users(
    client, auth_headers, second_user_headers
):
    with SessionLocal() as db:
        user, document = _user_document(db, "alice@example.com")
        task = Task(
            document_id=document.id,
            user_id=user.id,
            task_text="Submit resume",
            deadline="2026-10-14",
            deadline_time="",
            priority="HIGH",
            category="Placement",
        )
        db.add(task)
        db.flush()
        db.add(
            Notification(
                user_id=user.id,
                document_id=document.id,
                task_id=task.id,
                target_key=f"task:{task.id}",
                reminder_key=f"task:{task.id}:three_days:2026-10-14",
                title="Deadline reminder: Submit resume",
                message="Due 2026-10-14 (UTC).",
                stage="three_days",
                reminder_date="2026-10-14",
                deadline_at=datetime(2026, 10, 14, 9),
                email_status="disabled",
            )
        )
        db.commit()
        notification_id = db.query(Notification).one().id

    response = client.get("/api/notifications", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["target_type"] == "task"
    assert response.json()[0]["document_name"] == "placement-notice.pdf"

    assert client.get(
        "/api/notifications", headers=second_user_headers
    ).json() == []
    assert client.patch(
        f"/api/notifications/{notification_id}/read",
        headers=second_user_headers,
    ).status_code == 404
    assert client.get(
        "/api/notifications/unread-count", headers=auth_headers
    ).json() == {"unread_count": 1}
    assert client.patch(
        "/api/notifications/read-all", headers=auth_headers
    ).json() == {"success": True, "updated_count": 1}
    assert client.get(
        "/api/notifications/unread-count", headers=auth_headers
    ).json() == {"unread_count": 0}
    assert client.patch(
        f"/api/notifications/{notification_id}/read", headers=auth_headers
    ).json()["is_read"] is True


def test_desktop_delivery_requires_opt_in_and_is_idempotent(
    client, auth_headers
):
    with SessionLocal() as db:
        user, document = _user_document(db, "alice@example.com")
        task = Task(
            document_id=document.id,
            user_id=user.id,
            task_text="Submit application",
            deadline="2026-10-12",
            priority="HIGH",
            category="Placement",
        )
        db.add(task)
        db.flush()
        notification = Notification(
            user_id=user.id,
            document_id=document.id,
            task_id=task.id,
            target_key=f"task:{task.id}",
            reminder_key=f"task:{task.id}:one_day:2026-10-12",
            title="Reminder",
            message="Due soon.",
            stage="one_day",
            reminder_date="2026-10-12",
            deadline_at=datetime(2026, 10, 12, 9),
            email_status="disabled",
        )
        db.add(notification)
        db.commit()
        notification_id = notification.id

    assert client.post(
        f"/api/notifications/{notification_id}/desktop-delivered",
        headers=auth_headers,
    ).status_code == 403
    assert client.patch(
        "/api/reminder-preferences",
        headers=auth_headers,
        json={"desktop_enabled": True},
    ).status_code == 200
    first = client.post(
        f"/api/notifications/{notification_id}/desktop-delivered",
        headers=auth_headers,
    ).json()
    second = client.post(
        f"/api/notifications/{notification_id}/desktop-delivered",
        headers=auth_headers,
    ).json()
    assert first["delivered"] is True
    assert second["delivered"] is False


def test_scheduler_preserves_five_placement_dates_and_times():
    dates = [
        ("Placement Registration", "2026-10-12", ""),
        ("Resume Submission", "2026-10-14", ""),
        ("Placement Orientation", "2026-10-16", "10:00"),
        ("Internship Documents", "2026-10-18", ""),
        ("Aptitude Test", "2026-10-20", ""),
    ]
    with SessionLocal() as db:
        user, document = _user_document(db, "placement-reminders@example.com")
        db.add(
            ReminderPreference(
                user_id=user.id,
                enabled=True,
                remind_three_days=False,
                remind_one_day=False,
                remind_at_deadline=True,
                date_only_time="09:00",
                timezone="UTC",
            )
        )
        for title, deadline, deadline_time in dates:
            db.add(
                Task(
                    document_id=document.id,
                    user_id=user.id,
                    task_text=title,
                    deadline=deadline,
                    deadline_time=deadline_time,
                    priority="HIGH",
                    category="Placement",
                )
            )
        db.commit()

        for title, deadline, deadline_time in dates:
            hour, minute = (map(int, deadline_time.split(":")) if deadline_time else (9, 0))
            due = datetime.fromisoformat(
                f"{deadline}T{hour:02d}:{minute:02d}:00+00:00"
            )
            assert process_due_reminders(now=due, db=db) >= 1
            assert process_due_reminders(now=due, db=db) == 0

        saved = (
            db.query(Notification)
            .filter(Notification.user_id == user.id)
            .all()
        )
        assert {item.title.split(": ", 1)[-1] for item in saved} == {
            title for title, _, _ in dates
        }
        assert {
            (item.task.deadline, item.task.deadline_time)
            for item in saved
        } == set(dates_for_tasks(dates))


def dates_for_tasks(dates):
    return [(deadline, deadline_time) for _, deadline, deadline_time in dates]


def test_duplicate_standalone_deadline_is_skipped_but_distinct_notice_deadline_survives():
    now = datetime(2026, 10, 3, 9, tzinfo=timezone.utc)
    with SessionLocal() as db:
        user, document = _user_document(db, "standalone-reminders@example.com")
        task = Task(
            document_id=document.id,
            user_id=user.id,
            task_text="Placement Registration",
            deadline="2026-10-12",
            priority="HIGH",
            category="Placement",
        )
        db.add(task)
        db.flush()
        db.add(
            ReminderPreference(
                user_id=user.id,
                email_enabled=True,
                date_only_time="09:00",
                timezone="UTC",
            )
        )
        db.add_all(
            [
                Deadline(
                    document_id=document.id,
                    user_id=user.id,
                    deadline_date="2026-10-12",
                    description="Generic placement notice deadline",
                ),
                Deadline(
                    document_id=document.id,
                    user_id=user.id,
                    deadline_date="2026-10-06",
                    description="Overall notice deadline",
                ),
            ]
        )
        db.commit()

        process_due_reminders(now=now, db=db)
        saved = (
            db.query(Notification)
            .filter(Notification.user_id == user.id)
            .all()
        )
        assert len(saved) == 1
        assert saved[0].deadline.description == "Overall notice deadline"
        assert saved[0].deadline.deadline_date == "2026-10-06"
        assert saved[0].email_status == "not_configured"


def test_email_delivery_uses_configured_smtp_and_reports_delivery(monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            assert username == "smtp-user"
            assert password == "smtp-password"

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(config, "SMTP_CONFIGURED", True)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "SMTP_FROM", "reminders@example.test")
    monkeypatch.setattr(config, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "smtp-password")
    monkeypatch.setattr(config, "SMTP_USE_SSL", False)
    monkeypatch.setattr(config, "SMTP_USE_TLS", True)
    monkeypatch.setattr("app.services.reminder_service.smtplib.SMTP", FakeSMTP)

    with SessionLocal() as db:
        user, document = _user_document(db, "email-reminders@example.com")
        db.add(
            ReminderPreference(
                user_id=user.id,
                email_enabled=True,
                remind_three_days=False,
                remind_one_day=False,
                remind_at_deadline=True,
                date_only_time="09:00",
                timezone="UTC",
            )
        )
        db.add(
            Task(
                document_id=document.id,
                user_id=user.id,
                task_text="Submit resume",
                deadline="2026-10-14",
                priority="HIGH",
                category="Placement",
            )
        )
        db.commit()

        process_due_reminders(
            now=datetime(2026, 10, 14, 9, tzinfo=timezone.utc),
            db=db,
        )
        notification = db.query(Notification).filter_by(user_id=user.id).one()
        assert notification.email_status == "sent"
        assert notification.email_attempts == 1
        assert len(sent_messages) == 1
        assert sent_messages[0]["To"] == "email-reminders@example.com"
