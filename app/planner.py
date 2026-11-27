"""Single-user planning metadata; source tasks and events remain in their owning modules."""
from datetime import date, datetime, timezone
import os
from urllib.parse import urlsplit
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db
from .projects import Project
from .life_resources import PersonalGoal, HabitLog

router = APIRouter(prefix="/api/planner", tags=["planner"])
Key = Annotated[str, Field(pattern=r"^(school|tt|exam|project|goal|finance|habit|event|workout|local|payment)-[\w.-]{1,180}$")]
TextLine = Annotated[str, Field(min_length=1, max_length=180)]


class DayPlan(Base):
    __tablename__ = "planner_days"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    priorities: Mapped[list] = mapped_column(JSON)
    start_min: Mapped[int | None]
    end_min: Mapped[int | None]
    version: Mapped[int]


class WeekPlan(Base):
    __tablename__ = "planner_weeks"
    monday: Mapped[date] = mapped_column(Date, primary_key=True)
    objectives: Mapped[list] = mapped_column(JSON)
    achievements: Mapped[str] = mapped_column(Text)
    obstacles: Mapped[str] = mapped_column(Text)
    next_week: Mapped[str] = mapped_column(Text)
    version: Mapped[int]


class Area(Base):
    __tablename__ = "planner_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(String(300))
    color: Mapped[str] = mapped_column(String(7))
    icon: Mapped[str] = mapped_column(String(24))
    importance: Mapped[int]


class Placement(Base):
    __tablename__ = "planner_placements"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    scheduled: Mapped[date | None] = mapped_column(Date, index=True)
    minutes: Mapped[int | None]
    goal_id: Mapped[int | None] = mapped_column(ForeignKey(PersonalGoal.id, ondelete="SET NULL"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey(Project.id, ondelete="SET NULL"), index=True)
    energy: Mapped[str | None] = mapped_column(String(10))
    context: Mapped[str] = mapped_column(String(100), default="")
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    quadrant: Mapped[int | None]
    area_id: Mapped[int | None] = mapped_column(ForeignKey("planner_areas.id", ondelete="SET NULL"), index=True)
    version: Mapped[int]


class Focus(Base):
    __tablename__ = "planner_focus_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(200))
    target_minutes: Mapped[int]
    started: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resumed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed: Mapped[int]
    status: Mapped[str] = mapped_column(String(12))
    # A single active or paused session is shared across all devices.
    active_slot: Mapped[int | None] = mapped_column(unique=True)
    notes: Mapped[str] = mapped_column(String(500))


class Fields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Versioned(Fields):
    version: int = Field(ge=0)


class DayFields(Versioned):
    priorities: list[Key] = Field(max_length=3)
    start_min: int | None = Field(default=None, ge=0, lt=1440)
    end_min: int | None = Field(default=None, gt=0, le=1440)

    @model_validator(mode="after")
    def validate_values(self):
        if len(set(self.priorities)) != len(self.priorities):
            raise ValueError("Priorità duplicate")
        if (self.start_min is None) != (self.end_min is None) or (self.start_min is not None and self.end_min <= self.start_min):
            raise ValueError("Indica una finestra oraria valida")
        return self


class Objective(Fields):
    title: TextLine
    main: bool = True
    done: bool = False
    links: list[Key] = Field(default_factory=list, max_length=30)


class WeekFields(Versioned):
    objectives: list[Objective] = Field(default_factory=list, max_length=30)
    achievements: str = Field(default="", max_length=3000)
    obstacles: str = Field(default="", max_length=3000)
    next_week: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def top_three(self):
        if sum(o.main for o in self.objectives) > 3:
            raise ValueError("Al massimo tre obiettivi principali")
        return self


class PlaceFields(Versioned):
    goal_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    energy: Literal["bassa","media","alta"] | None = None
    context: str = Field(default="", max_length=100)
    dependencies: list[Key] = Field(default_factory=list, max_length=30)
    scheduled: date | None = None
    minutes: int | None = Field(default=None, ge=1, le=1440)
    quadrant: int | None = Field(default=None, ge=1, le=4)
    area_id: int | None = Field(default=None, gt=0)


def store(db, model, pk, value, fields):
    data = fields.model_dump(exclude={"version"})
    next_version = fields.version + 1
    if fields.version == 0:
        insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        statement = insert(model).values({pk.key: value, **data, "version": 1}).on_conflict_do_nothing(index_elements=[pk])
    else:
        statement = update(model).where(pk == value, model.version == fields.version).values(**data, version=next_version)
    if db.scalar(statement.returning(model.version)) is None:
        raise HTTPException(409, "Il piano è cambiato su un altro dispositivo. Ricarica e riprova.")
    db.commit()
    return {**data, "version": next_version}


def values(row, fields, fallback):
    if row is None:
        return fallback.model_dump()
    return {k: getattr(row,k) for k in fields.model_fields}


@router.get("/days/{day}")
def day_plan(day: date, db: Session = Depends(get_db)):
    return values(db.get(DayPlan, day), DayFields, DayFields(version=0, priorities=[]))


@router.put("/days/{day}")
def save_day(day: date, body: DayFields, db: Session = Depends(get_db)):
    return store(db, DayPlan, DayPlan.day, day, body)


def monday_only(day):
    if day.weekday():
        raise HTTPException(422, "Scegli il lunedì della settimana")


@router.get("/weeks")
def week_history(db: Session = Depends(get_db)):
    return db.scalars(select(WeekPlan.monday).order_by(WeekPlan.monday.desc())).all()


@router.get("/weeks/{monday}")
def week_plan(monday: date, db: Session = Depends(get_db)):
    monday_only(monday)
    return values(db.get(WeekPlan, monday), WeekFields, WeekFields(version=0))


@router.put("/weeks/{monday}")
def save_week(monday: date, body: WeekFields, db: Session = Depends(get_db)):
    monday_only(monday)
    return store(db, WeekPlan, WeekPlan.monday, monday, body)


@router.get("/placements")
def placements(db: Session = Depends(get_db)):
    return db.scalars(select(Placement).order_by(Placement.key)).all()


@router.put("/placements/{key}")
def place(key: Key, body: PlaceFields, db: Session = Depends(get_db)):
    if body.goal_id and not db.get(PersonalGoal, body.goal_id):
        raise HTTPException(422, "Obiettivo inesistente")
    if body.project_id and not db.get(Project, body.project_id):
        raise HTTPException(422, "Progetto inesistente")
    if body.area_id and not db.get(Area, body.area_id):
        raise HTTPException(422, "Area inesistente")
    if len(set(body.dependencies)) != len(body.dependencies):
        raise HTTPException(422, "Dipendenze duplicate")
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy import func
        db.execute(select(func.pg_advisory_xact_lock(16023014, 5)))
    if body.dependencies:
        graph = dict(db.execute(select(Placement.key, Placement.dependencies)).all())
        pending, seen = list(body.dependencies), set()
        while pending:
            node = pending.pop()
            if node == key:
                raise HTTPException(422, "Dipendenza circolare")
            if node not in seen:
                seen.add(node)
                pending.extend(graph.get(node, []))
    return store(db, Placement, Placement.key, key, body)


class AreaFields(Fields):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    color: str = Field(default="#38bdf8", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str = Field(default="", max_length=24)
    importance: int = Field(default=3, ge=1, le=5)


@router.get("/areas")
def areas(db: Session = Depends(get_db)):
    return db.scalars(select(Area).order_by(Area.id)).all()


def persist_area(db, row, body):
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Il nome dell’area è già in uso")
    return row


@router.post("/areas", status_code=201)
def new_area(body: AreaFields, db: Session = Depends(get_db)):
    return persist_area(db, Area(), body)


@router.put("/areas/{i}")
def edit_area(i: int, body: AreaFields, db: Session = Depends(get_db)):
    row = db.get(Area, i)
    if not row:
        raise HTTPException(404, "Area non trovata")
    return persist_area(db, row, body)


@router.delete("/areas/{i}", status_code=204)
def delete_area(i: int, db: Session = Depends(get_db)):
    row = db.get(Area, i)
    if not row:
        raise HTTPException(404, "Area non trovata")
    db.execute(update(Placement).where(Placement.area_id == i).values(area_id=None, version=Placement.version+1))
    db.delete(row)
    db.commit()


class FocusIn(Fields):
    source_key: Key
    target_minutes: int = Field(ge=1, le=360)
    notes: str = Field(default="", max_length=500)


def utcstamp(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def focus_out(row, now):
    elapsed = row.elapsed
    if row.resumed:
        elapsed += max(0, int((now - utcstamp(row.resumed)).total_seconds()))
    return {"id": row.id, "source_key": row.source_key, "target_minutes": row.target_minutes,
            "started": utcstamp(row.started), "ended": utcstamp(row.ended) if row.ended else None,
            "status": row.status, "elapsed": elapsed, "notes": row.notes}


@router.get("/focus")
def sessions(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    return [focus_out(row, now) for row in db.scalars(select(Focus).order_by(Focus.started.desc()))]


@router.post("/focus", status_code=201)
def start_focus(body: FocusIn, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    row = Focus(**body.model_dump(), started=now, resumed=now, elapsed=0, status="running", active_slot=1)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "C’è già una sessione focus attiva.")
    return focus_out(row, now)


@router.post("/focus/{i}/{action}")
def control_focus(i: int, action: Literal["pause","resume","complete","cancel"], db: Session = Depends(get_db)):
    row = db.get(Focus, i, with_for_update=True)
    if not row:
        raise HTTPException(404, "Sessione inesistente")
    allowed = {"pause":{"running"}, "resume":{"paused"}, "complete":{"running","paused"}, "cancel":{"running","paused"}}
    if row.status not in allowed[action]:
        raise HTTPException(409, "Operazione incompatibile con lo stato della sessione")
    now = datetime.now(timezone.utc)
    row.elapsed = focus_out(row, now)["elapsed"]
    row.resumed = now if action == "resume" else None
    row.status = {"pause":"paused","resume":"running","complete":"completed","cancel":"cancelled"}[action]
    if action in ("complete","cancel"):
        row.ended, row.active_slot = now, None
    if action == "complete":
        from .notifications import Notification
        db.add(Notification(category="task", title="Sessione focus conclusa",
                            message=f"{row.elapsed // 60} min registrati nel Life Planner."))
    db.commit()
    return focus_out(row, now)


from .events import PersonalEvent


class BlockLink(Base):
    __tablename__ = "planner_event_links"
    event_id: Mapped[int] = mapped_column(ForeignKey(PersonalEvent.id, ondelete="CASCADE"), primary_key=True)
    source_key: Mapped[str | None] = mapped_column(String(200))
    project_id: Mapped[int | None] = mapped_column(ForeignKey(Project.id, ondelete="SET NULL"))
    color: Mapped[str] = mapped_column(String(7))


class BlockIn(Fields):
    title: TextLine
    starts_at: datetime
    ends_at: datetime
    category: str = Field(default="planning", min_length=1, max_length=30)
    description: str = Field(default="", max_length=4000)
    source_key: Key | None = None
    project_id: int | None = Field(default=None, gt=0)
    color: str = Field(default="#38bdf8", pattern=r"^#[0-9a-fA-F]{6}$")
    allow_overlap: bool = False

    @model_validator(mode="after")
    def valid_range(self):
        if self.starts_at.utcoffset() is None or self.ends_at.utcoffset() is None or self.ends_at <= self.starts_at:
            raise ValueError("Servono due orari con fuso e la fine successiva all’inizio")
        return self


@router.get("/blocks")
def block_links(db: Session = Depends(get_db)):
    return db.scalars(select(BlockLink).join(PersonalEvent, PersonalEvent.id == BlockLink.event_id)).all()


def write_block(i, data, db):
    from sqlalchemy import func
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(16023014, 4)))
    if data.project_id is not None and not db.get(Project, data.project_id):
        raise HTTPException(422, "Progetto inesistente")
    link = db.get(BlockLink, i) if i else None
    event = db.get(PersonalEvent, i, with_for_update=True) if i else PersonalEvent(location="")
    if i and (link is None or event is None):
        raise HTTPException(404, "Blocco non trovato")
    start, end = utcstamp(data.starts_at), utcstamp(data.ends_at)
    overlap = select(PersonalEvent.id).where(PersonalEvent.starts_at < end,
        ((PersonalEvent.ends_at > start) | (PersonalEvent.ends_at.is_(None) & (PersonalEvent.starts_at >= start))))
    if i:
        overlap = overlap.where(PersonalEvent.id != i)
    if not data.allow_overlap and db.scalar(overlap.limit(1)) is not None:
        raise HTTPException(409, "Il blocco si sovrappone a un evento del calendario.")
    event.title, event.starts_at, event.ends_at = data.title, start, end
    event.category, event.description = data.category, data.description
    db.add(event)
    db.flush()
    link = link or BlockLink(event_id=event.id)
    link.source_key, link.project_id, link.color = data.source_key, data.project_id, data.color
    db.add(link)
    db.commit()
    return {"event_id": event.id}


@router.post("/blocks", status_code=201)
def create_block(data: BlockIn, db: Session = Depends(get_db)):
    return write_block(None, data, db)


@router.put("/blocks/{i}")
def change_block(i: int, data: BlockIn, db: Session = Depends(get_db)):
    return write_block(i, data, db)


@router.delete("/blocks/{i}", status_code=204)
def remove_block(i: int, db: Session = Depends(get_db)):
    link = db.get(BlockLink, i)
    if not link:
        raise HTTPException(404, "Blocco non trovato")
    event = db.get(PersonalEvent, i)
    db.delete(link)
    db.flush()
    if event:
        db.delete(event)
    db.commit()


@router.get("/overview/{day}")
def overview(day: date, zone: str = Query(default="Europe/Rome", max_length=80), db: Session = Depends(get_db)):
    from datetime import time, timedelta
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from sqlalchemy import func
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Fuso orario sconosciuto")
    monday = day - timedelta(days=day.weekday())
    end = monday + timedelta(days=7)
    week = db.get(WeekPlan, monday)
    daily = db.get(DayPlan, day)
    start_at = datetime.combine(monday, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_at = datetime.combine(end, time.min, tzinfo=tz).astimezone(timezone.utc)
    focus = db.scalar(select(func.sum(Focus.elapsed)).where(
        Focus.status == "completed", Focus.started >= start_at, Focus.started < end_at))
    completed_habits = db.scalar(select(func.count(HabitLog.id)).where(
        HabitLog.completed.is_(True), HabitLog.day >= monday, HabitLog.day < end))
    objectives = week.objectives if week else []
    return {"weekly_objectives": len(objectives), "weekly_objectives_done": sum(bool(o["done"]) for o in objectives),
            "habit_completions": completed_habits, "focus_minutes": (focus or 0)//60,
            "daily_priorities": len(daily.priorities) if daily else 0}


class ContextItem(Fields):
    title: TextLine
    source: str = Field(max_length=60)
    due: date | None = None


class Advice(Fields):
    consent: bool
    question: str = Field(min_length=1, max_length=800)
    day: date
    items: list[ContextItem] = Field(min_length=1, max_length=80)


def assistant_configuration() -> tuple[str, str]:
    url = os.getenv("NEXUS_AI_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("NEXUS_AI_MODEL", "").strip()
    try:
        parts = urlsplit(url)
        local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
        if (not parts.hostname or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or parts.scheme not in ({"https", "http"} if local else {"https"})):
            return "", ""
        _ = parts.port  # Validate explicitly configured ports before accepting the URL.
    except ValueError:
        return "", ""
    return url, model


@router.get("/assistant/status")
def assistant_status():
    return {"configured": all(assistant_configuration())}


@router.post("/assistant")
async def assistant(body: Advice):
    import httpx
    if not body.consent:
        raise HTTPException(422, "Serve la conferma per condividere il contesto selezionato.")
    url, model = assistant_configuration()
    if not url or not model:
        raise HTTPException(503, "Il provider AI di NEXUS non è configurato. Il piano locale è disponibile.")
    token = os.environ.get("NEXUS_AI_TOKEN")
    headers = {"Authorization": "Bearer " + token} if token else {}
    messages = [{"role":"system","content":"Sei il pianificatore di NEXUS. Rispondi in italiano usando soltanto il contesto selezionato. Cita gli elementi per titolo. Distingui fatti e proposte. Non puoi modificare alcun record."},
                {"role":"user","content":body.model_dump_json(exclude={"consent"})}]
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            result = await client.post(url+"/chat/completions", headers=headers,
                                       json={"model":model, "messages":messages,"stream":False})
            result.raise_for_status()
            answer = result.json()["choices"][0]["message"]["content"]
            if not isinstance(answer,str) or not answer.strip():
                raise ValueError()
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        raise HTTPException(502, "Il provider AI non ha restituito una risposta utilizzabile.")
    return {"answer": answer}


from sqlalchemy import event as sa_event

@sa_event.listens_for(Area.__table__, "after_create")
def defaults_for_local_sqlite(target, connection, **kwargs):
    if connection.dialect.name == "sqlite":
        names = ["Scuola","Lavoro","Salute","Sport","Finanze","Progetti","Relazioni","Vita sociale","Crescita personale","Hobby","Riposo"]
        connection.execute(target.insert(), [{"name":n,"description":"","color":"#38bdf8","icon":"","importance":3} for n in names])

def init_local_schema(engine):
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS planner_cleanup_event
            AFTER DELETE ON life_events BEGIN
            DELETE FROM planner_event_links WHERE event_id=OLD.id; END""")
        conn.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS planner_cleanup_project
            AFTER DELETE ON core_projects BEGIN
            UPDATE planner_event_links SET project_id=NULL WHERE project_id=OLD.id;
            UPDATE planner_placements SET project_id=NULL WHERE project_id=OLD.id; END""")
        conn.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS planner_cleanup_goal
            AFTER DELETE ON life_goals BEGIN
            UPDATE planner_placements SET goal_id=NULL WHERE goal_id=OLD.id; END""")
