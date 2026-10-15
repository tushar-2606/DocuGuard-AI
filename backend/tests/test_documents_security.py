from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import fitz
from fastapi.testclient import TestClient

import app.routers.documents as documents_router
from app.main import app


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_rejects_non_pdf(client, auth_headers):
    res = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_rejects_empty(client, auth_headers):
    res = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert res.status_code == 400


def test_upload_and_persist_for_owner(client, auth_headers):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2026.")
    res = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("notice.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["is_saved"] is True
    assert body["document_id"] is not None

    listed = client.get("/api/documents", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_repeated_pdf_upload_returns_existing_document(client, auth_headers):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2027.")
    first_upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("same.pdf", pdf, "application/pdf")},
    )
    assert first_upload.status_code == 200, first_upload.text
    first_response = first_upload.json()
    task_id = first_response["analysis"]["tasks"][0]["id"]
    completed = client.patch(
        f"/api/tasks/{task_id}/toggle",
        headers=auth_headers,
    )
    assert completed.status_code == 200

    duplicate_upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("same.pdf", pdf, "application/pdf")},
    )
    assert duplicate_upload.status_code == 200, duplicate_upload.text
    duplicate_response = duplicate_upload.json()

    assert duplicate_response["document_id"] == first_response["document_id"]
    assert duplicate_response["analysis"]["tasks"][0]["id"] == task_id
    assert duplicate_response["analysis"]["tasks"][0]["is_completed"] is True
    assert duplicate_response["content_hash"] == first_response["content_hash"]
    assert duplicate_response.keys() == first_response.keys()
    documents = client.get("/api/documents", headers=auth_headers).json()
    assert [doc["id"] for doc in documents] == [first_response["document_id"]]
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    matching = [task for task in tasks if task["document_id"] == first_response["document_id"]]
    assert len(matching) == len(first_response["analysis"]["tasks"]) == 1


def test_same_pdf_upload_by_different_users_creates_separate_documents(
    client, auth_headers, second_user_headers
):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2027.")
    uploads = [
        client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("same.pdf", pdf, "application/pdf")},
        )
        for headers in (auth_headers, second_user_headers)
    ]

    assert all(upload.status_code == 200 for upload in uploads)
    assert uploads[0].json()["document_id"] != uploads[1].json()["document_id"]


def test_concurrent_same_pdf_uploads_create_one_document(
    client, auth_headers, monkeypatch
):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2027.")
    barrier = Barrier(2)
    original_analyze_document = documents_router.analyze_document

    def synchronized_analysis(text):
        result = original_analyze_document(text)
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(documents_router, "analyze_document", synchronized_analysis)

    def upload():
        concurrent_client = TestClient(app)
        return concurrent_client.post(
            "/api/documents/upload",
            headers=auth_headers,
            files={"file": ("same.pdf", pdf, "application/pdf")},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(), range(2)))

    assert all(response.status_code == 200 for response in responses)
    document_ids = {response.json()["document_id"] for response in responses}
    assert len(document_ids) == 1
    documents = client.get("/api/documents", headers=auth_headers).json()
    assert [doc["id"] for doc in documents] == list(document_ids)


def test_cross_user_document_access_denied(client, auth_headers, second_user_headers):
    pdf = _make_pdf("Students must register by 01 June 2026.")
    upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("alice.pdf", pdf, "application/pdf")},
    )
    doc_id = upload.json()["document_id"]

    forbidden = client.get(f"/api/documents/{doc_id}", headers=second_user_headers)
    assert forbidden.status_code == 404

    delete_forbidden = client.delete(f"/api/documents/{doc_id}", headers=second_user_headers)
    assert delete_forbidden.status_code == 404


def test_task_toggle_ownership(client, auth_headers, second_user_headers):
    pdf = _make_pdf("Students must submit the form by 15 March 2026.")
    upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("tasks.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 200
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    assert len(tasks) >= 1
    task_id = tasks[0]["id"]

    denied = client.patch(f"/api/tasks/{task_id}/toggle", headers=second_user_headers)
    assert denied.status_code == 404
    denied_edit = client.patch(
        f"/api/tasks/{task_id}",
        headers=second_user_headers,
        json={"task": "Steal another user's task"},
    )
    assert denied_edit.status_code == 404
    denied_delete = client.delete(f"/api/tasks/{task_id}", headers=second_user_headers)
    assert denied_delete.status_code == 404

    ok = client.patch(f"/api/tasks/{task_id}/toggle", headers=auth_headers)
    assert ok.status_code == 200
    assert "is_completed" in ok.json()


def test_task_edit_and_delete(client, auth_headers):
    pdf = _make_pdf("Students must pay the fee by 20 April 2026.")
    client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("edit.pdf", pdf, "application/pdf")},
    )
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    assert tasks
    task_id = tasks[0]["id"]

    updated = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={
            "task": "Pay examination fee",
            "deadline": "2026-04-21",
            "priority": "HIGH",
            "review_status": "corrected",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["task"] == "Pay examination fee"
    assert body["deadline"] == "2026-04-21"
    assert body["review_status"] == "corrected"

    deleted = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
    assert deleted.status_code == 200
    remaining = client.get("/api/tasks", headers=auth_headers).json()
    assert all(t["id"] != task_id for t in remaining)


def test_task_review_completion_edits_and_relogin_persist(client, auth_headers):
    pdf = _make_pdf("Students must submit the examination form by 15 March 2027 at 5:30 PM.")
    upload = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("persist.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    task = client.get("/api/tasks", headers=auth_headers).json()[0]
    task_id = task["id"]
    assert task["deadline"] == "2027-03-15"
    assert task["deadline_time"] == "17:30"
    assert task["source_snippet"]
    assert task["page_number"] == 1
    assert task["extraction_method"] == "rule_based"
    assert task["review_status"] == "pending"

    accepted = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={"review_status": "accepted"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["review_status"] == "accepted"

    completed_once = client.patch(
        f"/api/tasks/{task_id}/toggle",
        headers=auth_headers,
    )
    assert completed_once.status_code == 200
    assert completed_once.json()["is_completed"] is True
    reopened = client.patch(
        f"/api/tasks/{task_id}/toggle",
        headers=auth_headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["is_completed"] is False

    rejected = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={"review_status": "rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"
    assert rejected.json()["is_completed"] is True

    completed = client.patch(f"/api/tasks/{task_id}/toggle", headers=auth_headers)
    assert completed.status_code == 200
    assert completed.json()["is_completed"] is False

    edited = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={
            "task": "Submit the corrected examination form",
            "deadline": "2027-03-16",
            "deadline_time": "16:45",
            "review_status": "corrected",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["task"] == "Submit the corrected examination form"
    assert edited.json()["deadline"] == "2027-03-16"
    assert edited.json()["deadline_time"] == "16:45"
    assert edited.json()["review_status"] == "corrected"

    invalid_date = client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={"deadline": "2027-02-30"},
    )
    assert invalid_date.status_code == 400

    login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert login.status_code == 200
    reauthenticated = {"Authorization": f"Bearer {login.json()['access_token']}"}
    refreshed = client.get("/api/tasks", headers=reauthenticated)
    assert refreshed.status_code == 200
    persisted = next(item for item in refreshed.json() if item["id"] == task_id)
    assert persisted["task"] == "Submit the corrected examination form"
    assert persisted["deadline"] == "2027-03-16"
    assert persisted["deadline_time"] == "16:45"
    assert persisted["review_status"] == "corrected"
    assert persisted["is_completed"] is False

    deleted = client.delete(f"/api/tasks/{task_id}", headers=reauthenticated)
    assert deleted.status_code == 200
    assert all(
        item["id"] != task_id
        for item in client.get("/api/tasks", headers=reauthenticated).json()
    )
