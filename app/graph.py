"""Read explicit relationships between application records."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .academic import StudyTask
from .db import get_db
from .events import PersonalEvent
from .inbox import InboxItem
from .models import Note
from .planner import BlockLink
from .projects import Project

router = APIRouter(prefix="/api/graph", tags=["graph"])


class Node(BaseModel):
    key: str
    title: str
    kind: str
    path: str


class Connection(BaseModel):
    origin: Node
    destination: Node


class GraphPage(BaseModel):
    connections: list[Connection]
    next_before: int | None


@router.get("", response_model=GraphPage)
def graph(q: str = Query("", max_length=100), before: int | None = Query(None, gt=0),
          relation: Literal["inbox", "project-blocks"] = "inbox",
          db: Session = Depends(get_db)):
    if relation == "project-blocks":
        query = (select(PersonalEvent.id, PersonalEvent.title, Project.id, Project.title)
                 .select_from(BlockLink).join(PersonalEvent, PersonalEvent.id == BlockLink.event_id)
                 .join(Project, Project.id == BlockLink.project_id))
        if q:
            query = query.where(or_(PersonalEvent.title.icontains(q, autoescape=True),
                                    Project.title.icontains(q, autoescape=True)))
        if before is not None:
            query = query.where(BlockLink.event_id < before)
        rows = db.execute(query.order_by(BlockLink.event_id.desc()).limit(51)).all()
        return GraphPage(connections=[
            Connection(origin=Node(key=f"event-{eid}", title=event, kind="Evento", path=f"/calendar?evento={eid}"),
                       destination=Node(key=f"project-{pid}", title=project, kind="Progetto", path=f"/projects?id={pid}"))
            for eid, event, pid, project in rows[:50]
        ], next_before=rows[49][0] if len(rows) > 50 else None)
    targets = (
        (Note, InboxItem.note_id, "Nota", "/knowledge?nota="),
        (Project, InboxItem.project_id, "Progetto", "/projects?id="),
        (PersonalEvent, InboxItem.event_id, "Evento", "/calendar?evento="),
        (StudyTask, InboxItem.task_id, "Attività", "/academic?sezione=agenda"),
    )
    query = select(InboxItem.id, InboxItem.title)
    linked, matches = [], [InboxItem.title.icontains(q, autoescape=True)]
    for model, foreign_key, _, _ in targets:
        query = query.add_columns(model.id, model.title).outerjoin(model, foreign_key == model.id)
        linked.append(model.id.is_not(None))
        matches.append(model.title.icontains(q, autoescape=True))
    query = query.where(or_(*linked))
    if q:
        query = query.where(or_(*matches))
    if before is not None:
        query = query.where(InboxItem.id < before)
    rows = db.execute(query.order_by(InboxItem.id.desc()).limit(51)).all()
    connections = []
    for row in rows[:50]:
        origin = Node(key=f"inbox-{row[0]}", title=row[1], kind="Inbox", path=f"/inbox?id={row[0]}")
        for index, (model, _, kind, path) in enumerate(targets):
            identifier, title = row[2 + 2*index:4 + 2*index]
            if identifier is not None:
                destination = Node(key=f"{model.__tablename__}-{identifier}", title=title, kind=kind,
                                   path=path + str(identifier) if path.endswith("=") else path)
                connections.append(Connection(origin=origin, destination=destination))
    return GraphPage(connections=connections, next_before=rows[49][0] if len(rows) > 50 else None)
