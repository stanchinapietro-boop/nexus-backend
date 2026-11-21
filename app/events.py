"""Eventi personali. Schema e percorsi condivisi con Life Planner Desktop."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .db import get_db
from .projects import CoreBase

router = APIRouter(prefix="/api/life/events", tags=["calendar"])


class PersonalEvent(CoreBase):
    __tablename__ = "life_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(30), default="personal")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(180), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=180)
    category: str = Field(default="personal", max_length=30)
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    location: str = Field(default="", max_length=180)
    description: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def chronological(self):
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("La fine evento precede l'inizio")
        self.starts_at = self.starts_at.astimezone(timezone.utc)
        if self.ends_at:
            self.ends_at = self.ends_at.astimezone(timezone.utc)
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    category: str
    starts_at: datetime
    ends_at: datetime | None
    location: str
    description: str

    @field_validator("starts_at", "ends_at")
    @classmethod
    def mark_utc(cls, stamp):
        if stamp is not None and stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp


@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.scalars(select(PersonalEvent).order_by(PersonalEvent.starts_at)).all()


@router.post("", response_model=EventOut, status_code=201)
def create_event(data: EventIn, db: Session = Depends(get_db)):
    event = PersonalEvent(**data.model_dump())
    db.add(event)
    db.commit()
    return event


@router.put("/{event_id}", response_model=EventOut)
def edit_event(event_id: int, data: EventIn, db: Session = Depends(get_db)):
    event = db.get(PersonalEvent, event_id)
    if event is None:
        raise HTTPException(404, "Evento non trovato")
    for key, value in data.model_dump().items():
        setattr(event, key, value)
    db.commit()
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(PersonalEvent, event_id)
    if event is None:
        raise HTTPException(404, "Evento non trovato")
    db.delete(event)
    db.commit()
