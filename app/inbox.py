"""Raccolta personale e conversione transazionale in nota."""
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import JSON, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .db import get_db
from .models import Note
from .academic import StudyTask, TaskMeta
from .projects import CoreBase, Project
from .events import PersonalEvent
from pydantic import AwareDatetime

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

Kind = Literal["task", "idea", "note", "reminder", "event", "expense", "project", "other"]
Status = Literal["new", "processing", "archived", "completed"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=48)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Content = Annotated[str, Field(max_length=20_000)]
Tags = Annotated[list[Tag], Field(max_length=20)]


class InboxBase(DeclarativeBase):
    """PostgreSQL viene aggiornato esplicitamente con migrations/001_inbox.sql."""


def utcnow():
    return datetime.now(timezone.utc)


class InboxItem(InboxBase):
    __tablename__ = "inbox_items"
    __table_args__ = (
        CheckConstraint("kind IN ('task','idea','note','reminder','event','expense','project','other')"),
        CheckConstraint("status IN ('new','processing','archived','completed')"),
        Index("ix_inbox_items_status_created", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="new")
    tags: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    source: Mapped[str] = mapped_column(String(80))
    destination: Mapped[str | None] = mapped_column(String(80))
    due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note_id: Mapped[int | None] = mapped_column(ForeignKey(Note.id, ondelete="SET NULL"))

    project_id: Mapped[int | None] = mapped_column(ForeignKey(Project.id, ondelete="SET NULL"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey(StudyTask.id, ondelete="SET NULL"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey(PersonalEvent.id, ondelete="SET NULL"))


def init_local_schema(engine):
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            CoreBase.metadata.create_all(conn)
            InboxItem.__table__.create(bind=conn, checkfirst=True)
            # Le installazioni SQLite esistenti possono usare foreign_keys=OFF.
            conn.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS inbox_clear_deleted_note
                AFTER DELETE ON notes
                BEGIN UPDATE inbox_items SET note_id = NULL WHERE note_id = OLD.id; END
            """)
            for target, column in (("core_projects", "project_id"), ("life_events", "event_id"), ("academic_tasks", "task_id")):
                conn.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS inbox_clear_{column} AFTER DELETE ON {target} "
                                     f"BEGIN UPDATE inbox_items SET {column} = NULL WHERE {column} = OLD.id; END")



class InboxFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("tags", check_fields=False)
    @classmethod
    def distinct_tags(cls, value):
        if value is None:
            return value
        result = {}
        for tag in value:
            result.setdefault(tag.casefold(), tag)
        return list(result.values())


class Capture(InboxFields):
    title: Title
    content: Content = ""
    kind: Kind = "other"
    tags: Tags = Field(default_factory=list)
    due_date: date | None = None
    source: Label = "inbox"
    destination: Label | None = None
    request_id: UUID = Field(default_factory=uuid4)


class Edit(InboxFields):
    title: Title | None = None
    content: Content | None = None
    kind: Kind | None = None
    status: Status | None = None
    tags: Tags | None = None
    due_date: date | None = None
    destination: Label | None = None

    @model_validator(mode="after")
    def reject_invalid_nulls(self):
        for key in self.model_fields_set - {"due_date", "destination"}:
            if getattr(self, key) is None:
                raise ValueError(f"Il campo {key} non può essere nullo")
        if not self.model_fields_set:
            raise ValueError("Nessuna modifica specificata")
        return self


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    kind: Kind
    status: Status
    tags: list[str]
    due_date: date | None
    source: str
    destination: str | None
    created_at: datetime
    updated_at: datetime
    converted_at: datetime | None
    note_id: int | None
    project_id: int | None
    task_id: int | None
    event_id: int | None

    @field_validator("created_at", "updated_at", "converted_at")
    @classmethod
    def normalize_timestamp(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def get_item(db, item_id):
    row = db.get(InboxItem, item_id)
    if row is None:
        raise HTTPException(404, "Elemento Inbox non trovato")
    return row


@router.get("", response_model=list[ItemOut])
def list_items(q: Annotated[str, Query(max_length=200)] = "", status: Status | None = None,
               kind: Kind | None = None, tag: Tag | None = None, db: Session = Depends(get_db)):
    query = select(InboxItem)
    if status:
        query = query.where(InboxItem.status == status)
    if kind:
        query = query.where(InboxItem.kind == kind)
    if q.strip():
        term = q.strip().lower()
        query = query.where(or_(func.lower(InboxItem.title).contains(term, autoescape=True),
                                func.lower(InboxItem.content).contains(term, autoescape=True)))
    rows = db.scalars(query.order_by(InboxItem.created_at.desc(), InboxItem.id.desc())).all()
    if tag:
        return [row for row in rows if any(label.casefold() == tag.casefold() for label in row.tags)]
    return rows


@router.post("", response_model=ItemOut, status_code=201)
def capture(data: Capture, response: Response, db: Session = Depends(get_db)):
    values = data.model_dump(exclude={"request_id"})
    digest = sha256(data.model_dump_json(exclude={"request_id"}).encode()).hexdigest()
    key = str(data.request_id)
    row = InboxItem(**values, request_id=key, request_hash=digest)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(InboxItem).where(InboxItem.request_id == key))
        if existing is None:
            raise
        if existing.request_hash != digest:
            raise HTTPException(409, "Identificativo già utilizzato per un altro elemento")
        response.status_code = 200
        return existing
    return row


@router.get("/{item_id}", response_model=ItemOut)
def read_item(item_id: int, db: Session = Depends(get_db)):
    return get_item(db, item_id)


@router.put("/{item_id}", response_model=ItemOut)
def edit_item(item_id: int, data: Edit, db: Session = Depends(get_db)):
    changed = db.execute(update(InboxItem).where(InboxItem.id == item_id)
                         .values(**data.model_dump(exclude_unset=True)))
    if not changed.rowcount:
        raise HTTPException(404, "Elemento Inbox non trovato")
    result = ItemOut.model_validate(get_item(db, item_id))
    db.commit()
    return result


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    changed = db.execute(delete(InboxItem).where(InboxItem.id == item_id))
    if not changed.rowcount:
        raise HTTPException(404, "Elemento Inbox non trovato")
    db.commit()


class EventTime(BaseModel):
    starts_at: AwareDatetime


def convert(item_id: int, target: str, db: Session, starts_at: datetime | None = None):
    # Un solo writer ottiene l'elemento. Destinazione e collegamento vengono salvati insieme.
    captured = db.execute(update(InboxItem).where(InboxItem.id == item_id, InboxItem.converted_at.is_(None))
                          .values(converted_at=utcnow(), status="completed", destination=target))
    item = get_item(db, item_id)
    id_field = target + "_id"
    if not captured.rowcount:
        if getattr(item, id_field) is None:
            raise HTTPException(409, "Elemento già elaborato")
        return item
    if target == "note":
        record = Note(title=item.title, content=item.content)
    elif target == "project":
        record = Project(title=item.title, description=item.content, target_date=item.due_date)
    elif target == "task":
        if len(item.title) > 160 or len(item.content) > 1000:
            raise HTTPException(422, "Per Academic usa un titolo entro 160 caratteri e un contenuto entro 1000.")
        record = StudyTask(title=item.title, kind="study", due_date=item.due_date)
    else:
        if len(item.title) > 180 or len(item.content) > 4000:
            raise HTTPException(422, "Per il calendario usa un titolo entro 180 caratteri e un contenuto entro 4000.")
        stamp = starts_at.astimezone(timezone.utc)
        record = PersonalEvent(title=item.title, description=item.content, starts_at=stamp)
    db.add(record)
    db.flush()
    if target == "task":
        db.add(TaskMeta(task_id=record.id, description=item.content))
    setattr(item, id_field, record.id)
    result = ItemOut.model_validate(item)
    db.commit()
    return result


@router.post("/{item_id}/note", response_model=ItemOut)
def convert_to_note(item_id: int, db: Session = Depends(get_db)):
    return convert(item_id, "note", db)


@router.post("/{item_id}/project", response_model=ItemOut)
def convert_to_project(item_id: int, db: Session = Depends(get_db)):
    return convert(item_id, "project", db)


@router.post("/{item_id}/task", response_model=ItemOut)
def convert_to_school_task(item_id: int, db: Session = Depends(get_db)):
    return convert(item_id, "task", db)


@router.post("/{item_id}/event", response_model=ItemOut)
def convert_to_event(item_id: int, timing: EventTime, db: Session = Depends(get_db)):
    return convert(item_id, "event", db, timing.starts_at)
