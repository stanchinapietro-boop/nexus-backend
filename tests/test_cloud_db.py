import pytest
from app.db import _url

def test_vercel_requires_explicit_postgres(monkeypatch):
    monkeypatch.setenv("VERCEL","1")
    monkeypatch.setenv("POSTGRES_URL","postgres://example/other")
    monkeypatch.delenv("DATABASE_URL",raising=False)
    with pytest.raises(RuntimeError):_url()
    monkeypatch.setenv("DATABASE_URL","sqlite:///local.db")
    with pytest.raises(RuntimeError):_url()
    monkeypatch.setenv("DATABASE_URL","postgres://example/intended")
    assert _url()=="postgresql+psycopg://example/intended"
