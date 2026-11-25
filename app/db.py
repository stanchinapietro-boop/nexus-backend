import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from .preview_db import validate_preview_target

load_dotenv()


def _url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "sqlite:///./nexus.db"
    if os.getenv("VERCEL_ENV") == "preview":
        validate_preview_target(os.getenv("DATABASE_URL", ""), os.getenv("NEXUS_PREVIEW_SUPABASE_REF", ""),
                                os.getenv("NEXUS_REAL_SUPABASE_REF", ""))
    if os.getenv("VERCEL") and not (os.getenv("DATABASE_URL") or "").startswith(("postgres://","postgresql://","postgresql+psycopg://")):
        raise RuntimeError("La versione cloud richiede DATABASE_URL PostgreSQL")
    for old in ("postgres://", "postgresql://"):
        if url.startswith(old):
            return "postgresql+psycopg://" + url[len(old):]
    return url


DATABASE_URL = _url()

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Serverless: una connessione per richiesta, niente pool che resta aperto.
    engine = create_engine(DATABASE_URL, poolclass=NullPool)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
