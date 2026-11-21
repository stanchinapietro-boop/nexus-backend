"""Attività ricostruite da record con data di creazione o modifica verificabile."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import literal, select, union_all
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .db import get_db
from .academic import AcademicNote
from .inbox import InboxItem
from .models import Note
from .projects import Project

router = APIRouter(prefix="/api/activity", tags=["activity"])
Module = Literal["inbox", "knowledge", "academic", "projects"]


class Activity(BaseModel):
    module: Module
    id: int
    title: str
    action: str
    timestamp: datetime
    to: str


@router.get("", response_model=list[Activity])
def recent(module: Module | None = None, limit: int = Query(8, ge=1, le=50), db: Session = Depends(get_db)):
    sources = {
        "projects": (Project, Project.updated_at, literal("Progetto aggiornato")),
        "knowledge": (Note, Note.created_at, literal("Nota creata")),
        "academic": (AcademicNote, AcademicNote.updated_at, literal("Appunto salvato")),
        "inbox": (InboxItem, InboxItem.updated_at, literal("Elemento Inbox salvato")),
    }
    statements = []
    for name, (model, stamp, label) in sources.items():
        if module and module != name:
            continue
        statements.append(select(literal(name).label("module"), model.id, model.title, stamp.label("stamp"), label.label("action")))
    events = union_all(*statements).subquery()
    rows = db.execute(select(events).order_by(events.c.stamp.desc(), events.c.module, events.c.id.desc()).limit(limit)).mappings()
    result = []
    for row in rows:
        target = {"projects": f"/projects?id={row['id']}", "inbox": f"/inbox?id={row['id']}", "knowledge": f"/knowledge?nota={row['id']}", "academic": "/academic?sezione=notes"}[row["module"]]
        stamp = row["stamp"]
        result.append(Activity(module=row["module"], id=row["id"], title=row["title"], action=row["action"],
                               timestamp=stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc), to=target))
    return result
