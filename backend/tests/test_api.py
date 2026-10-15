import json
from pathlib import Path

from tests.conftest import FIXTURES_DIR


def _upload(client, collection_id, filename):
    data = (FIXTURES_DIR / filename).read_bytes()
    return client.post(
        f"/api/collections/{collection_id}/documents",
        files={"file": (filename, data, "application/pdf")},
    )


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_list_and_delete_collection(client):
    resp = client.post("/api/collections", json={"name": "Course A"})
    assert resp.status_code == 201
    collection_id = resp.json()["id"]

    resp = client.get("/api/collections")
    assert any(c["id"] == collection_id for c in resp.json())

    resp = client.delete(f"/api/collections/{collection_id}")
    assert resp.status_code == 204

    resp = client.get(f"/api/collections/{collection_id}")
    assert resp.status_code == 404


def test_upload_rejects_non_pdf(client):
    collection_id = client.post("/api/collections", json={"name": "X"}).json()["id"]
    resp = client.post(
        f"/api/collections/{collection_id}/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_to_missing_collection_returns_404(client):
    resp = client.post(
        "/api/collections/does-not-exist/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 404


def test_full_pipeline_grounded_answer(client, fake_provider):
    collection_id = client.post("/api/collections", json={"name": "OS Course"}).json()["id"]
    upload_resp = _upload(client, collection_id, "operating_systems_notes.pdf")
    assert upload_resp.status_code == 201
    doc = upload_resp.json()
    assert doc["status"] == "indexed"
    assert doc["page_count"] == 6

    docs_resp = client.get(f"/api/collections/{collection_id}/documents")
    assert len(docs_resp.json()) == 1

    fake_provider["chat_response"] = _answer_with_real_chunk_id

    resp = client.post(f"/api/collections/{collection_id}/query", json={"question": "What causes a deadlock?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert len(body["claims"]) == 1
    assert body["claims"][0]["verification_status"] == "supported"
    assert body["claims"][0]["citation"]["page_number"] == 4

    delete_resp = client.delete(f"/api/documents/{doc['id']}")
    assert delete_resp.status_code == 204
    assert client.get(f"/api/collections/{collection_id}/documents").json() == []


def test_refusal_when_model_reports_unanswerable(client, fake_provider):
    collection_id = client.post("/api/collections", json={"name": "OS Course 2"}).json()["id"]
    _upload(client, collection_id, "operating_systems_notes.pdf")

    fake_provider["chat_response"] = json.dumps({"answerable": False, "answer_text": "", "claims": []})

    resp = client.post(f"/api/collections/{collection_id}/query", json={"question": "What is the capital of France?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is True
    assert body["claims"] == []


def test_malformed_llm_response_retries_then_refuses(client, fake_provider):
    collection_id = client.post("/api/collections", json={"name": "OS Course 3"}).json()["id"]
    _upload(client, collection_id, "operating_systems_notes.pdf")

    fake_provider["chat_response"] = "not valid json at all"

    resp = client.post(f"/api/collections/{collection_id}/query", json={"question": "What causes a deadlock?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is True
    assert body["retry_count"] >= 1
    # retried once (max_retry=1 by default) then refused -> 2 calls total
    assert len(fake_provider["chat_calls"]) == 2


def test_fabricated_quote_is_refused_not_presented_as_supported(client, fake_provider):
    collection_id = client.post("/api/collections", json={"name": "OS Course 4"}).json()["id"]
    _upload(client, collection_id, "operating_systems_notes.pdf")

    fake_provider["chat_response"] = lambda system, user: json.dumps(
        {
            "answerable": True,
            "answer_text": "Deadlocks are prevented by disabling all interrupts.",
            "claims": [
                {
                    "claim_text": "Deadlocks are prevented by disabling all interrupts.",
                    "chunk_id": _any_chunk_id(user),
                    "quote": "disabling all interrupts prevents every deadlock",
                }
            ],
        }
    )

    resp = client.post(f"/api/collections/{collection_id}/query", json={"question": "How are deadlocks prevented?"})
    body = resp.json()
    assert body["refused"] is True


def test_delete_collection_removes_uploaded_files_from_disk(client, db_session, fake_provider):
    from app.models import Document

    collection_id = client.post("/api/collections", json={"name": "Cleanup Test"}).json()["id"]
    doc = _upload(client, collection_id, "operating_systems_notes.pdf").json()

    file_path = Path(db_session.get(Document, doc["id"]).file_path)
    assert file_path.exists()

    resp = client.delete(f"/api/collections/{collection_id}")
    assert resp.status_code == 204
    assert not file_path.exists()


def test_query_against_missing_collection_returns_404(client):
    resp = client.post("/api/collections/does-not-exist/query", json={"question": "hi"})
    assert resp.status_code == 404


def _any_chunk_id(user_prompt: str) -> str:
    import re

    match = re.search(r"chunk_id=([0-9a-f-]+)", user_prompt)
    return match.group(1) if match else ""


def _answer_with_real_chunk_id(system: str, user_prompt: str) -> str:
    """Fake LLM responder used by tests that need both the generation call and the
    verification judge call to behave sensibly (the two calls share the same
    provider.chat() mock point, so the fake must branch on which prompt it's given)."""
    import re

    if "fact-checking judge" in system:
        return json.dumps({"status": "supported", "explanation": "The evidence directly supports the claim."})

    match = re.search(r"\[chunk_id=([0-9a-f-]+) \| document=[^|]+\| page=4\]", user_prompt)
    chunk_id = match.group(1) if match else _any_chunk_id(user_prompt)
    return json.dumps(
        {
            "answerable": True,
            "answer_text": "Deadlocks require four conditions.",
            "claims": [
                {
                    "claim_text": "Deadlocks require four conditions.",
                    "chunk_id": chunk_id,
                    "quote": "Four conditions must all hold simultaneously for a deadlock to occur",
                }
            ],
        }
    )
