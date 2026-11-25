"""Ricerca testuale nei dati NEXUS. Le fonti selezionano solo i campi da mostrare."""
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import academic, finance
from .db import get_db
from .inbox import InboxItem
from .life_resources import PersonalGoal
from .models import Note
from .projects import Project
from .events import PersonalEvent

router = APIRouter(prefix="/api/search", tags=["search"])
PER_CATEGORY = 8


class Result(BaseModel):
    id: int
    group: str
    title: str
    detail: str
    day: str | None
    to: str


class SearchResponse(BaseModel):
    results: list[Result]
    unavailable: list[str]
    per_category: int = PER_CATEGORY


@dataclass
class Source:
    label: str
    statement: object
    columns: tuple
    link: Callable[[int, str | None], str]


def source(label, model, title, detail, day, columns, to):
    """Ogni adapter può aggiungere join alla stessa forma di risultato."""
    statement = select(
        literal(label).label("category"), model.id.label("id"),
        title.label("title"), func.substr(detail, 1, 160).label("detail"),
        cast(day, String).label("day"),
    ).select_from(model)
    link = to if callable(to) else lambda _id, _day: to
    return Source(label, statement, columns, link)


def sources():
    c, t, e, g = academic.Course, academic.StudyTask, academic.AcademicExam, academic.Grade
    n, ag = academic.AcademicNote, academic.AcademicGoal
    tx, account, cat, goal = finance.Transaction, finance.Account, finance.Category, finance.Goal
    blank = literal("")
    no_date = literal(None)
    notes = source("Note", Note, Note.title, Note.content, Note.created_at, (Note.title, Note.content), lambda i, _: f"/knowledge?nota={i}")
    courses = source("Materie", c, c.name, c.teacher, no_date, (c.name, c.teacher), "/academic?sezione=courses")
    tasks = source("Attività scolastiche", t, t.title, c.name, t.due_date, (t.title, c.name),
                   lambda i, day: f"/calendar?giorno={day}#task-{i}" if day else "/academic?sezione=agenda")
    tasks.statement = tasks.statement.outerjoin(c, t.course_id == c.id).outerjoin(
        academic.TaskMeta, academic.TaskMeta.task_id == t.id
    ).where(t.done.is_(False), func.coalesce(academic.TaskMeta.status, "todo").not_in(("done", "cancelled")))
    tasks.columns += (academic.TaskMeta.description, academic.TaskMeta.notes)
    exams = source("Verifiche", e, e.title, c.name, e.exam_date, (e.title, e.topics, e.description, c.name),
                   lambda i, day: f"/calendar?giorno={day}#exam-{i}")
    exams.statement = exams.statement.join(c, e.course_id == c.id)
    grade_title = c.name + literal(" · ") + cast(g.value, String)
    grades = source("Voti", g, grade_title, g.description, g.day, (c.name, g.description, g.kind, cast(g.value, String)), "/academic?sezione=grades")
    grades.statement = grades.statement.join(c, g.course_id == c.id)
    materials = source("Appunti scolastici", n, n.title, c.name, n.updated_at, (n.title, n.content, n.tags, c.name), "/academic?sezione=notes")
    materials.statement = materials.statement.outerjoin(c, n.course_id == c.id)
    academic_goals = source("Obiettivi scolastici", ag, func.coalesce(func.nullif(ag.label, ""), literal("Media ") + cast(ag.target_average, String)), c.name, no_date,
                            (ag.label, c.name, ag.school_year, cast(ag.target_average, String)), "/academic?sezione=analytics")
    academic_goals.statement = academic_goals.statement.outerjoin(c, ag.course_id == c.id)
    transaction_type = case((tx.type == "income", "Entrata"), else_="Uscita")
    transactions = source("Transazioni", tx, func.coalesce(func.nullif(tx.note, ""), cat.name, transaction_type),
                          account.name, tx.day, (tx.note, cat.name, account.name, transaction_type),
                          lambda i, day: f"/finance/movimenti?mese={day[:7]}#tx-{i}")
    transactions.statement = transactions.statement.join(account, tx.account_id == account.id).outerjoin(cat, tx.category_id == cat.id)
    savings = source("Obiettivi di risparmio", goal, goal.name, blank, goal.deadline, (goal.name,), "/finance/obiettivi")
    projects = source("Progetti", Project, Project.title, Project.description, Project.updated_at,
                      (Project.title, Project.description, Project.milestone), lambda i, _: f"/projects?id={i}")
    events = source("Eventi personali", PersonalEvent, PersonalEvent.title, PersonalEvent.location, PersonalEvent.starts_at,
                    (PersonalEvent.title, PersonalEvent.description, PersonalEvent.location), lambda i, _: f"/calendar?evento={i}")
    personal_goals = source("Obiettivi personali", PersonalGoal, PersonalGoal.title, PersonalGoal.category, PersonalGoal.due_date,
                            (PersonalGoal.title, PersonalGoal.description, PersonalGoal.category), "/life?tab=obiettivi")
    return [projects, events, notes, personal_goals, tasks, exams, courses, grades, materials, academic_goals, transactions, savings]


def select_matches(adapter, words):
    statement = adapter.statement
    for word in words:
        statement = statement.where(or_(*(column.icontains(word, autoescape=True) for column in adapter.columns)))
    matches = statement.order_by(statement.selected_columns.id.desc()).limit(PER_CATEGORY).subquery()
    return select(matches)


def results_for(db, adapters, words):
    queries = [select_matches(adapter, words) for adapter in adapters]
    query = union_all(*queries) if len(queries) > 1 else queries[0]
    links = {adapter.label: adapter.link for adapter in adapters}
    rows = []
    for row in db.execute(query).mappings():
        day = row["day"][:10] if row["day"] else None
        rows.append(Result(id=row["id"], group=row["category"], title=row["title"],
                           detail=row["detail"] or "", day=day, to=links[row["category"]](row["id"], day)))
    return rows


@router.get("", response_model=SearchResponse)
def search(q: str = Query(min_length=2, max_length=100), db: Session = Depends(get_db)):
    words = list(dict.fromkeys(q.strip().split()))
    if len(q.strip()) < 2:
        return SearchResponse(results=[], unavailable=[])
    rows = results_for(db, sources(), words)
    inbox = source("Inbox", InboxItem, InboxItem.title, InboxItem.content, InboxItem.created_at,
                   (InboxItem.title, InboxItem.content, cast(InboxItem.tags, String)), lambda i, _: f"/inbox?id={i}")
    try:
        # La ricerca delle altre entità resta disponibile durante l'aggiornamento dello schema Inbox.
        with db.begin_nested():
            rows.extend(results_for(db, [inbox], words))
    except SQLAlchemyError:
        return SearchResponse(results=rows, unavailable=["Inbox"])
    return SearchResponse(results=rows, unavailable=[])
