from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import app
from app.models import Note


@pytest.fixture()
def store(tmp_path: Path):
    engine = create_engine("sqlite:///" + str(tmp_path / "notifications.sqlite"),
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    # Il secondo avvio non deve raddoppiare il trigger.
    Base.metadata.create_all(engine)

    def connection():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = connection
    try:
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_notifications_workflow(store):
    client, engine = store
    assert client.get("/api/notifications").json() == []
    assert client.get("/api/notifications/unread-count").json() == {"count": 0}
    with Session(engine) as session:
        session.add(Note(title="Annullata", content=""))
        session.flush()
        session.rollback()
    assert client.get("/api/notifications").json() == []
    notes = [client.post("/api/notes", json={"title": title}).json()["id"] for title in ("Una", "Due", "Tre")]
    rows = client.get("/api/notifications").json()
    assert [row["note_id"] for row in rows] == list(reversed(notes))
    first, second, last = [row["id"] for row in rows]
    assert rows[0]["message"] == "Tre" and rows[0]["created_at"].endswith(("Z", "+00:00"))
    assert client.get("/api/notifications/unread-count").json() == {"count": 3}
    assert [row["id"] for row in client.get("/api/notifications", params={"before": first, "limit": 1}).json()] == [second]
    assert client.get("/api/notifications?category=task").json() == []
    read = client.put(f"/api/notifications/{first}/read", json={"read": True}).json()
    assert read["read_at"] and read["read_at"].endswith(("Z", "+00:00"))
    assert client.put(f"/api/notifications/{first}/read", json={"read": True}).json()["read_at"] == read["read_at"]
    assert [row["id"] for row in client.get("/api/notifications?unread=false").json()] == [first]
    assert client.put("/api/notifications/read-all").status_code == 204
    assert client.get("/api/notifications?unread=true").json() == []
    assert client.put(f"/api/notifications/{first}/read", json={"read": False}).json()["read_at"] is None
    assert client.get("/api/notifications/unread-count").json() == {"count": 1}
    assert client.delete(f"/api/notifications/{first}").status_code == 204
    assert len(client.get("/api/notes").json()) == 3
    assert client.delete(f"/api/notes/{notes[0]}").status_code == 204
    assert [row["id"] for row in client.get("/api/notifications").json()] == [second]
    assert client.delete(f"/api/notifications/{last}").status_code == 404
    assert client.put(f"/api/notifications/{last}/read", json={"read": True}).status_code == 404
    assert client.get("/api/notifications?category=invalid").status_code == 422
    assert client.get("/api/notifications?before=0").status_code == 422


def test_notifications_require_session(store):
    from app.auth import require_auth
    client, _ = store
    app.dependency_overrides.pop(require_auth, None)
    for method, path, body in [
        ("GET", "", None), ("GET", "/unread-count", None),
        ("PUT", "/read-all", None), ("PUT", "/1/read", {"read": True}), ("DELETE", "/1", None),
    ]:
        assert client.request(method, "/api/notifications" + path, json=body).status_code == 401
