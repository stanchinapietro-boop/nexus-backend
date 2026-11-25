import pytest
from app.db import _url

PREVIEW = "a" * 20
REAL = "b" * 20


@pytest.mark.parametrize("address,expected,valid", [
    (f"user@db.{PREVIEW}.supabase.co/postgres?sslmode=require", PREVIEW, True),
    (f"user.{PREVIEW}@region.pooler.supabase.com/postgres?sslmode=verify-full", PREVIEW, True),
    (f"user@db.{REAL}.supabase.co/postgres?sslmode=require", REAL, False),
    (f"user@db.{REAL}.supabase.co/postgres?sslmode=require", PREVIEW, False),
    (f"user@db.{PREVIEW}.supabase.co/postgres?sslmode=require&host=other", PREVIEW, False),
    (f"user@db.{PREVIEW}.supabase.co/postgres", PREVIEW, False),
    ("user@other.example/postgres?sslmode=require", PREVIEW, False),
    (f"user@db.{PREVIEW}.supabase.co/postgres?sslmode=require", "", False),
])
def test_preview_connection_before_database_access(monkeypatch, address, expected, valid):
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setenv("NEXUS_REAL_SUPABASE_REF", REAL)
    monkeypatch.setenv("NEXUS_PREVIEW_SUPABASE_REF", expected)
    monkeypatch.setenv("DATABASE_URL", "postgresql://" + address)
    if valid:
        assert _url().startswith("postgresql+psycopg://")
    else:
        with pytest.raises(RuntimeError):
            _url()
