from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.inbox import init_local_schema
from app.main import app


@pytest.fixture
def inbox_client(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "inbox-test.db"),
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    init_local_schema(engine)
    init_local_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with session() as db:
            yield db

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), engine
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        engine.dispose()


def test_inbox_create_search_update_archive_delete(inbox_client):
    client, engine = inbox_client
    catalog = inspect(engine)
    assert "ix_inbox_items_status_created" in {i["name"] for i in catalog.get_indexes("inbox_items")}
    assert catalog.get_foreign_keys("inbox_items")[0]["referred_table"] == "notes"
    response = client.post("/api/inbox", json={"title": " Un progetto ", "content": "Finire al 100%",
                                               "tags": [" Studio ", "studio"], "due_date": "2026-12-01"})
    assert response.status_code == 201
    row = response.json()
    assert row["title"] == "Un progetto" and row["tags"] == ["Studio"] and row["status"] == "new"
    assert date.fromisoformat(row["due_date"])
    assert client.post("/api/inbox", json={"title": "Altro"}).status_code == 201
    path = f"/api/inbox/{row['id']}"
    assert client.put(path, json={"status": "processing", "kind": "project", "due_date": None}).json()["due_date"] is None
    assert [r["id"] for r in client.get("/api/inbox", params={"q": "%", "tag": "studio", "kind": "project",
                                                               "status": "processing"}).json()] == [row["id"]]
    assert client.put(path, json={"status": "archived"}).json()["status"] == "archived"
    assert client.get(path).status_code == 200
    assert client.delete(path).status_code == 204
    assert client.delete(path).status_code == 404
    assert client.get(path).status_code == 404


def test_idempotent_retry_and_atomic_conversion(inbox_client):
    client, _ = inbox_client
    payload = {"title": "Conserva questo", "content": "Testo", "request_id": str(uuid4())}
    row = client.post("/api/inbox", json=payload).json()
    assert client.post("/api/inbox", json=payload).status_code == 200
    assert client.post("/api/inbox", json={**payload, "title": "Diversa"}).status_code == 409
    path = f"/api/inbox/{row['id']}"
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: client.post(path + "/note"), range(3)))
    assert all(r.status_code == 200 for r in results)
    note_ids = {r.json()["note_id"] for r in results}
    assert len(note_ids) == 1
    note_id = note_ids.pop()
    assert client.get(path).json()["status"] == "completed"
    assert client.get("/api/notes").json()[0]["content"] == "Testo"
    assert len(client.get("/api/notes").json()) == 1
    assert client.delete(f"/api/notes/{note_id}").status_code == 204
    row = client.get(path).json()
    assert row["note_id"] is None and row["converted_at"]
    assert client.post(path + "/note").status_code == 409
    assert client.get("/api/notes").json() == []


def test_inbox_validation_and_missing_items(inbox_client):
    client, _ = inbox_client
    for payload in [{"title": " "}, {"title": "A", "kind": "bad"}, {"title": "A", "tags": [" "]},
                    {"title": "A", "status": "new"}, {"title": "A", "request_id": "bad"}]:
        assert client.post("/api/inbox", json=payload).status_code == 422
    row = client.post("/api/inbox", json={"title": "A"}).json()
    path = f"/api/inbox/{row['id']}"
    for payload in [{}, {"status": None}, {"title": ""}, {"tags": ["x" * 49]}, {"tags": None}]:
        assert client.put(path, json=payload).status_code == 422
    assert client.put("/api/inbox/99", json={"title": "A"}).status_code == 404
    assert client.post("/api/inbox/99/note").status_code == 404


def test_preview_requires_session_for_inbox(inbox_client):
    from app.auth import require_auth
    client, _ = inbox_client
    app.dependency_overrides.pop(require_auth, None)
    assert client.get("/api/inbox").status_code == 401
    assert client.post("/api/inbox", json={"title": "Test"}).status_code == 401
    assert client.put("/api/inbox/1", json={"title": "Test"}).status_code == 401
    assert client.post("/api/inbox/1/note").status_code == 401
    assert client.delete("/api/inbox/1").status_code == 401


def test_all_destinations_and_mixed_retry(inbox_client):
    client, _ = inbox_client
    destinations = (("project", "project_id", "/api/projects"), ("event", "event_id", "/api/life/events"),
                    ("task", "task_id", "/api/academic/tasks"))
    for destination, column, collection in destinations:
        row = client.post("/api/inbox", json={"title": "Core integrazione", "content": "Contenuto"}).json()
        path = f"/api/inbox/{row['id']}/{destination}"
        timing = {"starts_at": "2026-12-04T16:30:00+01:00"} if destination == "event" else None
        response = client.post(path, json=timing)
        assert response.status_code == 200, response.text
        linked = response.json()[column]
        assert client.post(path, json=timing).json()[column] == linked
        assert client.post(f"/api/inbox/{row['id']}/note").status_code == 409
        assert any(item["id"] == linked for item in client.get(collection).json())
        assert client.delete(f"{collection}/{linked}").status_code == 204
        assert client.get(f"/api/inbox/{row['id']}").json()[column] is None


def test_search_activity_and_projects(inbox_client):
    client, _ = inbox_client
    item = client.post("/api/inbox", json={"title": "Bozza riunione"}).json()
    note = client.post("/api/notes", json={"title": "Verbale riunione"}).json()
    project = client.post("/api/projects", json={"title": "Riunione", "milestone": "Revisione"}).json()
    assert {row["group"] for row in client.get("/api/search?q=riunione").json()["results"]} >= {"Progetti", "Note", "Inbox"}
    assert client.get("/api/search?q=x").status_code == 422
    feed = client.get("/api/activity").json()
    assert {row["module"] for row in feed} >= {"projects", "inbox", "knowledge"}
    assert client.get("/api/activity?module=knowledge").json()[0]["id"] == note["id"]
    assert client.get("/api/activity?module=inbox").json()[0]["id"] == item["id"]
    path = f"/api/projects/{project['id']}"
    assert client.put(path, json={"title": "Aggiornato", "status": "completed"}).json()["progress"] == 100
    assert client.put(path, json={"title": "Aggiornato", "progress": 120}).status_code == 422
    assert client.delete(path).status_code == 204
