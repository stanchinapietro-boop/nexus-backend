"""Single-owner calendar reminders. Dispatch runs in PostgreSQL, independently of HTTP."""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db

router = APIRouter(prefix="/api/automations", tags=["automations"])


class Reminder(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    enabled: bool = False
    lead_minutes: int = Field(default=30, ge=5, le=1440)
    category: str = Field(default="", max_length=30)
    version: int = Field(default=0, ge=0)


class Run(BaseModel):
    event_id: int
    starts_at: datetime
    status: str
    attempts: int
    checked_at: datetime
    error_code: str | None


class Overview(BaseModel):
    available: bool
    rule: Reminder | None = None
    runs: list[Run] = Field(default_factory=list)


def available(db: Session) -> bool:
    return os.getenv("NEXUS_CALENDAR_REMINDERS") == "1" and db.get_bind().dialect.name == "postgresql"


def read_rule(db: Session) -> Reminder:
    row = db.execute(text("SELECT enabled, lead_minutes, category, version FROM public.nexus_calendar_reminder WHERE id=1")).mappings().one_or_none()
    return Reminder.model_validate(dict(row)) if row else Reminder()


@router.get("", response_model=Overview)
def overview(db: Session = Depends(get_db)):
    if not available(db):
        return Overview(available=False)
    runs = db.execute(text("""
        SELECT event_id, starts_at, status, attempts, checked_at, error_code
        FROM public.nexus_reminder_runs ORDER BY checked_at DESC, event_id DESC LIMIT 50
    """)).mappings()
    return Overview(available=True, rule=read_rule(db), runs=[Run(**row) for row in runs])


@router.put("/calendar-reminder", response_model=Reminder)
def configure(change: Reminder, db: Session = Depends(get_db)):
    if not available(db):
        raise HTTPException(404, "Automazioni non abilitate in questo ambiente")
    # Serialize first creation and rule changes with the worker, including deactivation.
    db.execute(text("SELECT pg_advisory_xact_lock(16023014, 8)"))
    prior = read_rule(db)
    if change.version != prior.version:
        raise HTTPException(409, "Regola modificata in un’altra sessione. Ricarica prima di salvare.")
    db.execute(text("""
        INSERT INTO public.nexus_calendar_reminder (id, enabled, lead_minutes, category, version)
        VALUES (1, :enabled, :lead_minutes, :category, :version + 1)
        ON CONFLICT (id) DO UPDATE SET enabled=EXCLUDED.enabled, lead_minutes=EXCLUDED.lead_minutes,
            category=EXCLUDED.category, version=EXCLUDED.version
    """), change.model_dump())
    result = read_rule(db)
    db.commit()
    return result
