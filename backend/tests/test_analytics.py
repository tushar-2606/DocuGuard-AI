import csv
import io

import fitz

from app.database import SessionLocal
from app.models.db_models import Document, Task, User


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_dashboard_stats_scoped_to_user(client, auth_headers, second_user_headers):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2026.")
    client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("a.pdf", pdf, "application/pdf")},
    )

    alice = client.get("/api/dashboard/stats", headers=auth_headers)
    assert alice.status_code == 200
    alice_stats = alice.json()
    assert alice_stats["total_documents"] >= 1
    assert alice_stats["pending_tasks"] + alice_stats["completed_tasks"] >= 1
    assert "tasks_by_priority" in alice_stats
    assert "tasks_by_category" in alice_stats

    bob = client.get("/api/dashboard/stats", headers=second_user_headers)
    assert bob.status_code == 200
    bob_stats = bob.json()
    assert bob_stats["total_documents"] == 0
    assert bob_stats["pending_tasks"] == 0


def test_csv_export_sanitizes_and_returns_rows(client, auth_headers):
    pdf = _make_pdf("Students must register by 01 May 2026.")
    client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("export.pdf", pdf, "application/pdf")},
    )
    res = client.get("/api/dashboard/export/tasks.csv", headers=auth_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    text = res.text
    assert "task" in text.lower()
    assert "confidence_heuristic" in text


def test_csv_export_uses_extracted_and_persisted_deadline_fields(client, auth_headers):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Students must attend the placement orientation on 16 October 2026 "
        "at 10:00 AM.",
    )
    page.insert_text((72, 90), "Students must submit the examination form.")
    pdf = doc.tobytes()
    doc.close()
    upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("placement.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    response = client.get(
        "/api/dashboard/export/tasks.csv", headers=auth_headers
    )
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text, newline="")))

    orientation = next(row for row in rows if "orientation" in row["task"].lower())
    undated = next(row for row in rows if "examination form" in row["task"].lower())
    assert orientation["deadline"] == "2026-10-16"
    assert orientation["deadline_time"] == "10:00"
    assert undated["deadline"] == ""
    assert undated["deadline_time"] == ""


def test_csv_export_preserves_deadline_time_and_escapes_existing_rows(
    client, auth_headers
):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "alice@example.com").one()
        document = Document(
            user_id=user.id,
            filename='csv, "quoted".pdf',
            safe_filename='csv, "quoted".pdf',
            document_type="OTHER",
            pages=1,
            text_length=0,
            summary="",
        )
        db.add(document)
        db.flush()
        db.add_all(
            [
                Task(
                    document_id=document.id,
                    user_id=user.id,
                    task_text='Review "signed", forms\nand attachments',
                    deadline="2026-10-16",
                    deadline_time="10:00",
                    priority="MEDIUM",
                    category="Documents",
                    confidence=0.75,
                    source_snippet='Submit "signed", forms\nby 16 October 2026.',
                ),
                Task(
                    document_id=document.id,
                    user_id=user.id,
                    task_text="Review the notice",
                    deadline=None,
                    deadline_time=None,
                    priority="LOW",
                    category="General",
                    confidence=0.6,
                    source_snippet="Review the notice.",
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/dashboard/export/tasks.csv", headers=auth_headers
    )
    assert response.status_code == 200
    assert "charset=utf-8" in response.headers.get("content-type", "")

    rows = list(csv.DictReader(io.StringIO(response.text, newline="")))
    assert rows[0]["document"] == 'csv, "quoted".pdf'
    assert rows[0]["task"] == 'Review "signed", forms\nand attachments'
    assert rows[0]["deadline"] == "2026-10-16"
    assert rows[0]["deadline_time"] == "10:00"
    assert rows[0]["source_snippet"] == 'Submit "signed", forms\nby 16 October 2026.'
    assert rows[1]["task"] == "Review the notice"
    assert rows[1]["deadline"] == ""
    assert rows[1]["deadline_time"] == ""
