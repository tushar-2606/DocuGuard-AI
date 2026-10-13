import fitz


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
