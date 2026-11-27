"""Read-only comparisons for the authenticated NEXUS workspace."""
from datetime import date, datetime, time, timedelta, timezone
from enum import IntEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from .academic import StudySession
from .db import get_db
from .events import PersonalEvent
from .life_resources import Workout
from .models import Note

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class Window(IntEnum):
    week = 7
    month = 30
    quarter = 90


class Period(BaseModel):
    start: date
    end: date
    notes: int
    events: int
    study: int
    workouts: int


class Comparison(BaseModel):
    current: Period
    previous: Period


@router.get("", response_model=Comparison)
def comparison(end: date, days: Window = Window.week, zone: str = Query("UTC", max_length=100),
               db: Session = Depends(get_db)):
    try:
        tz = ZoneInfo(zone)
        after = end + timedelta(days=1)
        middle = after - timedelta(days=days)
        first = middle - timedelta(days=days)
        instants = [datetime.combine(day, time.min, tz).astimezone(timezone.utc)
                    for day in (first, middle, after)]
    except (ZoneInfoNotFoundError, ValueError, OverflowError):
        raise HTTPException(422, "Intervallo o fuso orario non valido.")

    def counts(metric, column, boundaries, *filters):
        start, split, stop = boundaries
        return (select(literal(metric).label("metric"), func.count().filter(column >= split).label("current"),
                       func.count().filter(column < split).label("previous"))
                .where(column >= start, column < stop, *filters))

    # Each aggregate reads only its date range. UNION ALL keeps both periods and
    # all four modules on one PostgreSQL statement snapshot.
    query = counts("notes", Note.created_at, instants).union_all(
        counts("events", PersonalEvent.starts_at, instants),
        counts("study", StudySession.ended_at, instants, StudySession.state == "completed"),
        counts("workouts", Workout.day, (first, middle, after), Workout.completed.is_(True)),
    )
    rows = {row.metric: row for row in db.execute(query)}
    return Comparison(
        current=Period(start=middle, end=end, **{key: row.current for key, row in rows.items()}),
        previous=Period(start=first, end=middle - timedelta(days=1),
                        **{key: row.previous for key, row in rows.items()}),
    )
