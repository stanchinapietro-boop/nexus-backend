"""Avvisi personali. Le notifiche delle note nascono nella loro stessa transazione."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import DateTime, ForeignKey, Index, String, event, func, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .db import Base, get_db
from .models import Note

Category = Literal["task", "event", "deadline", "project", "finance", "academic", "system", "ai", "automation"]
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationsBase(DeclarativeBase):
    """Su PostgreSQL la migrazione 002 gestisce questo schema."""


class Notification(NotificationsBase):
    __tablename__ = "core_notifications"
    __table_args__ = (
        Index("ix_core_notifications_read_id", "read_at", "id"),
        Index("ix_core_notifications_category_id", "category", "id"),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(500))
    note_id: Mapped[int | None] = mapped_column(ForeignKey(Note.id, ondelete="CASCADE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@event.listens_for(Base.metadata, "after_create")
def create_local_notifications(metadata, connection, **kwargs):
    if connection.dialect.name != "sqlite":
        return
    NotificationsBase.metadata.create_all(connection)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS nexus_note_added AFTER INSERT ON notes
        BEGIN
          INSERT INTO core_notifications (category, title, message, note_id)
          VALUES ('system', 'Nota salvata', NEW.title, NEW.id);
        END
    """)
    # SQLite consente connessioni con la verifica delle foreign key disattivata.
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS nexus_note_removed AFTER DELETE ON notes
        BEGIN DELETE FROM core_notifications WHERE note_id = OLD.id; END
    """)


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: Category
    title: str
    message: str
    note_id: int | None
    created_at: datetime
    read_at: datetime | None

    @field_validator("created_at", "read_at")
    @classmethod
    def timestamp_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ReadChange(BaseModel):
    read: bool


@router.get("", response_model=list[NotificationOut])
def list_notifications(category: Category | None = None, unread: bool | None = None,
                       before: int | None = Query(None, ge=1), limit: int = Query(40, ge=1, le=100),
                       db: Session = Depends(get_db)):
    query = select(Notification)
    if category is not None:
        query = query.where(Notification.category == category)
    if unread is not None:
        query = query.where(Notification.read_at.is_(None) if unread else Notification.read_at.is_not(None))
    if before is not None:
        query = query.where(Notification.id < before)
    return db.scalars(query.order_by(Notification.id.desc()).limit(limit)).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db)):
    return {"count": db.scalar(select(func.count(Notification.id)).where(Notification.read_at.is_(None)))}


@router.put("/read-all", status_code=204)
def mark_all_read(db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    db.commit()


@router.put("/{notification_id}/read", response_model=NotificationOut)
def set_read(notification_id: int, change: ReadChange, db: Session = Depends(get_db)):
    # Aggiornamento atomico: un secondo clic su "letta" conserva il primo timestamp.
    stamp = func.coalesce(Notification.read_at, func.now()) if change.read else None
    changed = db.scalar(update(Notification).where(Notification.id == notification_id)
                        .values(read_at=stamp).returning(Notification))
    if changed is None:
        raise HTTPException(404, "Notifica non trovata")
    db.commit()
    return changed


@router.delete("/{notification_id}", status_code=204)
def delete_notification(notification_id: int, db: Session = Depends(get_db)):
    notice = db.get(Notification, notification_id)
    if notice is None:
        raise HTTPException(404, "Notifica non trovata")
    db.delete(notice)
    db.commit()
