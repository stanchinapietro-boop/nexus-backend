"""Single-owner cloud settings and an opaque workspace revision."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from .db import get_db

router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.get("/state")
def state(db: Session = Depends(get_db)):
    if db.get_bind().dialect.name != "postgresql":
        return {"mode":"local","workspace":None,"revision":0,"preferences":{},"version":0}
    return dict(db.execute(text("SELECT 'cloud' AS mode, workspace, revision, preferences, version FROM nexus_sync WHERE id=1")).mappings().one())

class PreferenceChange(BaseModel):
    version: int = Field(ge=0)
    patch: dict

@router.patch("/preferences")
def preferences(body: PreferenceChange, db: Session = Depends(get_db)):
    allowed = set("theme badges quietFrom quietTo accent hiddenTabs hiddenWidgets compactSidebar favoritePaths navOrder recentCommands dashboardOrder dashboardHidden dashboardWide density timeZone clock dateFormat tasksView tasksUrgency".split())
    patch=json.dumps(body.patch,allow_nan=False)
    if not body.patch or set(body.patch)-allowed or len(patch)>16000:
        raise HTTPException(422,"Preferenze non valide")
    if db.get_bind().dialect.name != "postgresql":
        raise HTTPException(409,"Il server usa un archivio locale")
    changed=db.execute(text("""UPDATE nexus_sync SET preferences=preferences || CAST(:patch AS jsonb),
                         version=version+1 WHERE id=1 AND version=:version RETURNING version"""),
                         {"patch":patch,"version":body.version}).scalar()
    if changed is None:
        raise HTTPException(409,"Preferenze cambiate su un altro dispositivo. Rileggi prima di riprovare.")
    db.commit()
    return state(db)

from fastapi import Request, Response
from sqlalchemy import event

def guard_revision(request: Request, response: Response, db: Session = Depends(get_db)):
    expected = request.headers.get("X-Nexus-Revision")
    if expected is None or request.method in {"GET","HEAD","OPTIONS"} or db.get_bind().dialect.name != "postgresql":
        return
    row = db.execute(text("SELECT workspace, revision FROM nexus_sync WHERE id=1 FOR UPDATE")).one()
    if expected != f"{row.workspace}/{row.revision}":
        raise HTTPException(409,"Un altro dispositivo ha modificato i dati. Ricarica la sezione prima di salvare.")
    def before_commit(session):
        session.flush()
        revision=session.scalar(text("SELECT revision FROM nexus_sync WHERE id=1"))
        response.headers["X-Nexus-Revision"]=f"{row.workspace}/{revision}"
    event.listen(db,"before_commit",before_commit)
