import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, require_auth, verify_password
from app.db import Base, get_db
from app.main import app

CODE, PW = "c" * 20, "una-password-lunga-1"


@pytest.fixture()
def raw(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("SETUP_CODE", CODE)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_hash_is_salted_and_verifies():
    a, b = hash_password(PW), hash_password(PW)
    assert a != b and PW not in a
    assert verify_password(PW, a) and not verify_password("altra", a)


def test_setup_login_logout_flow(raw):
    assert raw.get("/api/auth/status").json()["setup_required"] is True
    assert raw.get("/api/notes").status_code == 401
    assert raw.post("/api/auth/setup", json={"code": "sbagliato", "password": PW}).status_code == 403
    assert raw.post("/api/auth/setup", json={"code": CODE, "password": PW}).status_code == 200
    assert raw.get("/api/notes").status_code == 200
    assert raw.post("/api/auth/setup", json={"code": CODE, "password": PW}).status_code == 409
    raw.post("/api/auth/logout")
    assert raw.get("/api/notes").status_code == 401
    assert raw.post("/api/auth/login", json={"password": "no"}).status_code == 401
    assert raw.post("/api/auth/login", json={"password": PW}).status_code == 200
    assert raw.get("/api/notes").status_code == 200


def test_lock_after_too_many_failures(raw):
    raw.post("/api/auth/setup", json={"code": CODE, "password": PW})
    raw.post("/api/auth/logout")
    for _ in range(5):
        assert raw.post("/api/auth/login", json={"password": "no"}).status_code == 401
    assert raw.post("/api/auth/login", json={"password": PW}).status_code == 429


def test_short_password_rejected(raw):
    assert raw.post("/api/auth/setup", json={"code": CODE, "password": "corta"}).status_code == 422
