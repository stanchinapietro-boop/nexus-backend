"""Registro progetti e prossima milestone del Command Center."""
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Date, DateTime, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from .db import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])
State = Literal["idea", "planning", "active", "paused", "completed", "archived"]


class CoreBase(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc)


class Project(CoreBase):
    __tablename__ = "core_projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="idea")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    milestone: Mapped[str] = mapped_column(String(200), default="")
    target_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    status: State = "idea"
    progress: int = Field(default=0, ge=0, le=100)
    milestone: str = Field(default="", max_length=200)
    target_date: date | None = None

    @model_validator(mode="after")
    def completion(self):
        if self.status == "completed":
            self.progress = 100
        return self


class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def aware_timestamp(cls, stamp):
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id.desc())).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectIn, db: Session = Depends(get_db)):
    project = Project(**data.model_dump())
    db.add(project)
    db.commit()
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def edit_project(project_id: int, data: ProjectIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Progetto non trovato")
    for key, value in data.model_dump().items():
        setattr(project, key, value)
    db.commit()
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Progetto non trovato")
    db.delete(project)
    db.commit()
