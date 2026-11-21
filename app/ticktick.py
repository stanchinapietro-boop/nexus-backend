"""Integrazione TickTick tramite Open API ufficiale (OAuth2, scope tasks:read tasks:write)."""
import os
import secrets
import hashlib
import json
import time as clock
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, JSON, BigInteger, delete
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db

router = APIRouter(prefix="/api/ticktick", tags=["ticktick"])
API = "https://api.ticktick.com/open/v1"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
SCOPE = "tasks:read tasks:write"
STATE_KEY = "ticktick_pending_oauth"


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"
    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    access_token: Mapped[str] = mapped_column(String(2000))


class TickSnapshot(Base):
    __tablename__ = "ticktick_sync_snapshot"
    connection: Mapped[str] = mapped_column(String(64), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSON)


class AuthError(Exception):
    pass


def cfg():
    return (os.getenv("TICKTICK_CLIENT_ID", ""), os.getenv("TICKTICK_CLIENT_SECRET", ""),
            os.getenv("TICKTICK_REDIRECT_URI", "http://localhost:8000/api/ticktick/callback"))


def tz_name() -> str:
    return os.getenv("TICKTICK_TIMEZONE", "Europe/Rome")


def _stored(db: Session):
    return db.get(IntegrationToken, "ticktick")


def _env_token() -> str:
    return os.getenv("TICKTICK_TOKEN", "").strip()


def _token(db: Session) -> str:
    row = _stored(db)
    if not row and _env_token():
        return _env_token()
    if not row:
        raise HTTPException(401, "TickTick non collegato")
    return row.access_token


def _req(token: str, method: str, path: str, **kw):
    r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {token}"}, timeout=15, **kw)
    if r.status_code in (401, 403):
        raise AuthError()
    if r.status_code >= 400:
        raise HTTPException(502, f"TickTick ha risposto {r.status_code}")
    return r.json() if r.content else None


def _guard(db: Session, fn):
    try:
        return fn()
    except AuthError:
        raise HTTPException(424, "TickTick ha rifiutato il token o i permessi. Ricollega l’account oppure verifica il token configurato.")
    except httpx.HTTPError:
        raise HTTPException(502, "TickTick non raggiungibile")


def parse_due(value: str | None) -> date | None:
    """Legge le date di TickTick (con o senza millesimi, es. 2026-12-01T10:15:00.000+0000)."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).astimezone(ZoneInfo(tz_name())).date()
        except ValueError:
            continue
    return None  # formato inatteso: il task resta visibile, senza scadenza


def fingerprint(task):
    return hashlib.sha256(json.dumps({k:task.get(k) for k in ("id","projectId","title","content","desc","startDate","dueDate","priority","status","etag","items","tags","reminders","timeZone","repeatFlag","isAllDay")},sort_keys=True,separators=(",",":")).encode()).hexdigest()


def normalize(t: dict, project: dict, today: date) -> dict:
    due = parse_due(t.get("dueDate"))
    return {"revision":fingerprint(t),"id": t["id"], "project_id": project["id"], "project_name": project.get("name", ""),
            "project_color": project.get("color") or "#8d8d94", "title": t.get("title", ""),
            "priority": t.get("priority", 0), "due_date": due.isoformat() if due else None,
            "overdue": bool(due and due < today)}


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    due: date | None = None
    priority: int = Field(default=0, ge=0, le=5)


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {"configured": bool(_env_token() or (cfg()[0] and cfg()[1])),
            "connected": bool(_env_token()) or _stored(db) is not None}


@router.get("/login")
def login(db: Session = Depends(get_db)):
    cid, _, redir = cfg()
    if not cid:
        raise HTTPException(400, "TICKTICK_CLIENT_ID mancante in apps/api/.env")
    st = secrets.token_urlsafe(16)
    digest = hashlib.sha256(st.encode()).hexdigest()
    db.merge(IntegrationToken(provider=STATE_KEY, access_token=f"{int(clock.time())}:{digest}"))
    db.commit()
    q = urlencode({"scope": SCOPE, "client_id": cid, "state": st, "redirect_uri": redir, "response_type": "code"})
    return RedirectResponse(f"{AUTH_URL}?{q}")


@router.get("/callback")
def callback(code: str = "", state: str = "", db: Session = Depends(get_db)):
    front = os.getenv("FRONTEND_URL", "http://localhost:5173")
    pending = db.get(IntegrationToken, STATE_KEY)
    stamp, _, digest = (pending.access_token if pending else "").partition(":")
    if not (code and state and stamp.isdigit() and 0 <= clock.time()-int(stamp) <= 600 and
            secrets.compare_digest(hashlib.sha256(state.encode()).hexdigest(), digest)):
        return RedirectResponse(f"{front}/tasks?ticktick=errore")
    consumed = db.scalar(delete(IntegrationToken).where(IntegrationToken.provider==STATE_KEY,
                         IntegrationToken.access_token==pending.access_token).returning(IntegrationToken.provider))
    db.commit()
    if not consumed:
        return RedirectResponse(f"{front}/tasks?ticktick=errore")
    cid, secret, redir = cfg()
    try:
        r = httpx.post(TOKEN_URL, auth=(cid, secret), timeout=15, data={
            "code": code, "grant_type": "authorization_code", "scope": SCOPE, "redirect_uri": redir})
        token = r.json()["access_token"]
    except Exception:
        return RedirectResponse(f"{front}/tasks?ticktick=errore")
    row = _stored(db)
    if row: row.access_token = token
    else: db.add(IntegrationToken(provider="ticktick", access_token=token))
    db.commit()
    return RedirectResponse(f"{front}/tasks?ticktick=ok")


@router.delete("/connection", status_code=204)
def disconnect(db: Session = Depends(get_db)):
    row = _stored(db)
    if row:
        db.delete(row); db.commit()


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tok = _token(db)
    today = datetime.now(ZoneInfo(tz_name())).date()

    started = clock.time_ns()
    connection = hashlib.sha256(tok.encode()).hexdigest()

    def fetch():
        projects = [p for p in _req(tok, "GET", "/project") if not p.get("closed") and (p.get("kind") or "TASK").upper() == "TASK"]
        with ThreadPoolExecutor(max_workers=6) as ex:
            datas = list(ex.map(lambda p: _req(tok, "GET", f"/project/{p['id']}/data"), projects))
        warnings = []
        lists = {p["id"]: p for p in projects}
        tasks = {}
        def collect(rows, fallback):
            for t in rows:
                pid = t.get("projectId") or fallback
                if not pid or not t.get("id") or t.get("status",0) != 0:
                    continue
                project = lists.setdefault(pid, {"id":pid,"name":"Inbox" if pid.lower().startswith("inbox") else pid})
                tasks[(pid,t["id"])] = normalize(t,project,today)
        # Cross-project view can include Inbox even when /project omits it.
        try:
            extra = _req(tok,"POST","/task/filter",json={"status":[0]})
            if not isinstance(extra,list):
                raise ValueError()
            collect(extra,None)
            if len(extra)>=200:
                warnings.append("Ricerca globale al limite di 200 risultati. Copertura delle liste non elencate da verificare.")
        except (HTTPException, ValueError, httpx.HTTPError):
            warnings.append("Ricerca globale indisponibile. Sono visibili le liste lette per progetto.")
        for project, data in zip(projects,datas):
            if not isinstance(data,dict) or not isinstance(data.get("tasks"),list):
                raise HTTPException(502,"Risposta progetto TickTick incompleta. Riprova.")
            collect(data["tasks"],project["id"])
        completed = {}
        try:
            recent = _req(tok,"POST","/task/completed",json={"startDate":(datetime.now(ZoneInfo(tz_name()))-timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S%z")})
            if not isinstance(recent,list):
                raise ValueError()
            for item in recent:
                pid=item.get("projectId")
                if pid and item.get("id"):
                    completed[(pid,item["id"])]=normalize(item,lists.get(pid,{"id":pid,"name":pid}),today)
            if len(recent)>=200:
                warnings.append("Storico dei completamenti al limite di 200 risultati.")
        except (HTTPException, ValueError, httpx.HTTPError):
            warnings.append("Storico dei completamenti indisponibile.")
        out = sorted(tasks.values(),key=lambda t:(t["due_date"] or "9999",-t["priority"]))
        return {"today":today.isoformat(),"week_end":(today+timedelta(days=7)).isoformat(),
                "completed":list(completed.values()),"synced_at":datetime.now(ZoneInfo(tz_name())).isoformat(),"warnings":warnings,
                "projects":[{"id":p["id"],"name":p["name"],"color":p.get("color")} for p in lists.values()],"tasks":out}

    try:
        result = _guard(db, fetch)
    except HTTPException as exc:
        previous=db.get(TickSnapshot, connection)
        if previous is None or exc.status_code != 502:
            raise
        return {**previous.payload,"warnings":[*previous.payload.get("warnings",[]),
                "Lettura TickTick fallita. Visualizzi l’ultima copia salvata."]}
    if not result["warnings"]:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert=pg_insert if db.get_bind().dialect.name=="postgresql" else sqlite_insert
        statement=insert(TickSnapshot).values(connection=connection,revision=started,payload=result)
        db.execute(statement.on_conflict_do_update(index_elements=[TickSnapshot.connection],
                   set_={"revision":started,"payload":result},where=TickSnapshot.revision<started))
        db.commit()
    return result


@router.post("/tasks", status_code=201)
def create_task(d: TaskIn, db: Session = Depends(get_db)):
    tok = _token(db)
    body: dict = {"title": d.title, "priority": d.priority}
    if d.project_id:
        body["projectId"] = d.project_id
    if d.due:
        s = datetime.combine(d.due, time(0), tzinfo=ZoneInfo(tz_name())).strftime("%Y-%m-%dT%H:%M:%S%z")
        body.update(startDate=s, dueDate=s, isAllDay=True, timeZone=tz_name())
    _guard(db, lambda: _req(tok, "POST", "/task", json=body))
    return {"ok": True}


@router.post("/tasks/{project_id}/{task_id}/complete")
def complete_task(project_id: str, task_id: str, db: Session = Depends(get_db)):
    tok = _token(db)
    _guard(db, lambda: _req(tok, "POST", f"/project/{project_id}/task/{task_id}/complete"))
    return {"ok": True}

class RenameTask(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    revision: str = Field(pattern="^[0-9a-f]{64}$")


@router.patch("/tasks/{project_id}/{task_id}")
def rename_task(project_id:str, task_id:str, body:RenameTask, db:Session=Depends(get_db)):
    token=_token(db)
    def rename():
        row=_req(token,"GET",f"/project/{project_id}/task/{task_id}")
        if not isinstance(row,dict) or row.get("id")!=task_id or row.get("projectId")!=project_id or fingerprint(row)!=body.revision:
            raise HTTPException(409,"La task è cambiata su TickTick. Aggiorna prima di modificare.")
        # Preserve fields from the fresh read. Never regenerate an entire local list.
        _req(token,"POST",f"/task/{task_id}",json={**row,"title":body.title})
        return {"ok":True}
    return _guard(db,rename)
