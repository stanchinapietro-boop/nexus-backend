"""Single-owner cloud settings and an opaque workspace revision."""
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter
from sqlalchemy import text
from sqlalchemy.orm import Session
from .db import get_db

router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.get("/state")
def state(db: Session = Depends(get_db)):
    if db.get_bind().dialect.name != "postgresql":
        return {"mode":"local","workspace":None,"revision":0,"preferences":{},"version":0}
    return dict(db.execute(text("SELECT 'cloud' AS mode, workspace, revision, preferences, version FROM nexus_sync WHERE id=1")).mappings().one())

ProfileId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,36}$")]
Entry = Annotated[str, StringConstraints(max_length=160)]
Order = Annotated[list[Entry], Field(max_length=128)]
Theme = Literal["dark", "midnight", "aurora", "cyberpunk", "matrix", "titanium", "ocean", "minimal", "light", "oled"]


Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Colors = dict[Literal["ink", "panel", "raised", "line", "text", "mute", "sidebar"], Hex]


class SavedTheme(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    theme: Theme
    accent: Hex
    colors: Colors


class Appearance(BaseModel):
    colors: Colors = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid", strict=True)
    theme: Theme
    accent: Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
    compactSidebar: bool
    favoritePaths: Order
    navOrder: Order
    hiddenTabs: Order
    dashboardOrder: Order
    dashboardHidden: Order
    dashboardWide: Order
    density: Literal["standard", "compact"]


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: ProfileId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    appearance: Appearance


profiles_adapter = TypeAdapter(Annotated[list[Profile], Field(min_length=1, max_length=24)])
theme_adapter = TypeAdapter(Theme)

class PreferenceChange(BaseModel):
    version: int = Field(ge=0)
    patch: dict

@router.patch("/preferences")
def preferences(body: PreferenceChange, db: Session = Depends(get_db)):
    allowed = set("savedThemes colors profiles activeProfile theme badges quietFrom quietTo accent hiddenTabs hiddenWidgets compactSidebar favoritePaths navOrder recentCommands dashboardOrder dashboardHidden dashboardWide density timeZone clock dateFormat tasksView tasksUrgency".split())
    patch=json.dumps(body.patch,allow_nan=False)
    if not body.patch or set(body.patch)-allowed or len(patch) > (128000 if "profiles" in body.patch else 16000):
        raise HTTPException(422,"Preferenze non valide")
    try:
        if "colors" in body.patch:
            TypeAdapter(Colors).validate_python(body.patch["colors"])
        if "savedThemes" in body.patch:
            library = TypeAdapter(Annotated[list[SavedTheme], Field(max_length=24)]).validate_python(body.patch["savedThemes"])
            if len({t.name for t in library}) != len(library):
                raise ValueError("duplicate theme name")
        if "theme" in body.patch:
            theme_adapter.validate_python(body.patch["theme"])
        if "profiles" in body.patch:
            profiles = profiles_adapter.validate_python(body.patch["profiles"])
            ids = {profile.id for profile in profiles}
            if len(ids) != len(profiles) or body.patch.get("activeProfile") not in ids:
                raise ValueError("invalid profile selection")
        elif "activeProfile" in body.patch:
            raise ValueError("profile switch requires the profile list")
    except ValueError:
        raise HTTPException(422, "Configurazione workspace o tema non valida") from None
    if db.get_bind().dialect.name != "postgresql":
        raise HTTPException(409,"Il server usa un archivio locale")
    changed=db.execute(text("""UPDATE nexus_sync SET preferences=preferences || CAST(:patch AS jsonb),
                         version=version+1 WHERE id=1 AND version=:version RETURNING 'cloud' AS mode, workspace, revision, preferences, version"""),
                         {"patch":patch,"version":body.version}).mappings().one_or_none()
    if changed is None:
        raise HTTPException(409,"Preferenze cambiate su un altro dispositivo. Rileggi prima di riprovare.")
    db.commit()
    return dict(changed)

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
