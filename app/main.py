from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from . import finance
from . import academic
from . import auth
from . import ticktick
from .db import Base, engine, get_db


_ready = False


def init_db() -> None:
    """Crea le tabelle e i dati iniziali. Parte alla prima richiesta (funziona anche su Vercel)."""
    global _ready
    if _ready:
        return
    Base.metadata.create_all(bind=engine)
    finance.seed()
    _ready = True


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="NEXUS LIFE OS API", version="0.1.0", lifespan=lifespan)

# Solo localhost e reti private (LAN). Da restringere in produzione.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ensure_ready(request, call_next):
    if not _ready and request.url.path.startswith("/api") and request.url.path != "/api/health":
        await run_in_threadpool(init_db)
    return await call_next(request)


protected = [Depends(auth.require_auth)]
app.include_router(auth.router)
app.include_router(finance.router, dependencies=protected)
app.include_router(academic.router, dependencies=protected)
app.include_router(ticktick.router, dependencies=protected)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/notes", dependencies=protected, response_model=list[schemas.NoteOut])
def list_notes(db: Session = Depends(get_db)):
    return db.scalars(select(models.Note).order_by(models.Note.id.desc())).all()


@app.post("/api/notes", dependencies=protected, response_model=schemas.NoteOut, status_code=201)
def create_note(data: schemas.NoteIn, db: Session = Depends(get_db)):
    note = models.Note(**data.model_dump())
    db.add(note)
    db.commit()
    return note


@app.put("/api/notes/{note_id}", dependencies=protected, response_model=schemas.NoteOut)
def update_note(note_id: int, data: schemas.NoteIn, db: Session = Depends(get_db)):
    note = db.get(models.Note, note_id)
    if not note:
        raise HTTPException(404, "Nota non trovata")
    note.title, note.content = data.title, data.content
    db.commit()
    return note


@app.delete("/api/notes/{note_id}", dependencies=protected, status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(models.Note, note_id)
    if not note:
        raise HTTPException(404, "Nota non trovata")
    db.delete(note)
    db.commit()
