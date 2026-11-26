"""Authenticated, opt-in recording of observed volleyball skills."""
import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import ForeignKey, String, Uuid, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db
from .life_resources import Workout

router = APIRouter(prefix="/api/life/volley", tags=["volley"])
Skill = Literal["serve", "receive", "attack", "block"]


class Sample(Base):
    __tablename__ = "volley_skill_samples"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey(Workout.id, ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(12))
    attempts: Mapped[int]
    successful: Mapped[int]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    skill: Skill
    attempts: int = Field(strict=True, ge=1, le=10000)
    successful: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def valid_count(self):
        if self.successful > self.attempts:
            raise ValueError("Le riuscite superano i tentativi")
        return self


class Total(BaseModel):
    skill: Skill
    attempts: int
    successful: int


def enabled():
    return os.getenv("NEXUS_VOLLEY_METRICS") == "1"


@router.get("/capabilities")
def capabilities():
    return {"metrics": enabled()}


def session_workout(workout_id: int, db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(404, "Metriche disattivate")
    workout = db.get(Workout, workout_id, with_for_update={"read": True})
    if not workout or workout.sport.strip().lower() not in {"volley", "volleyball", "pallavolo", "beach volley"}:
        raise HTTPException(404, "Allenamento Volley non trovato")
    return workout


@router.get("/{workout_id}/metrics", response_model=list[Total])
def totals(workout: Workout = Depends(session_workout), db: Session = Depends(get_db)):
    rows = db.execute(select(Sample.skill, func.sum(Sample.attempts).label("attempts"),
                             func.sum(Sample.successful).label("successful"))
                      .where(Sample.workout_id == workout.id).group_by(Sample.skill).order_by(Sample.skill))
    return list(rows.mappings())


@router.post("/{workout_id}/metrics", response_model=list[Total])
def record(data: Observation, workout: Workout = Depends(session_workout), db: Session = Depends(get_db)):
    values = dict(workout_id=workout.id, **data.model_dump())
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(Sample).values(**values).on_conflict_do_nothing(index_elements=[Sample.id]))
    stored = db.get(Sample, data.id)
    if not stored or any(getattr(stored, key) != value for key, value in values.items()):
        raise HTTPException(409, "Identificativo già utilizzato per una serie diversa")
    result = totals(workout, db)
    db.commit()
    return result
