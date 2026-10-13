import fitz


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
