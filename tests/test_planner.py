from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.inbox import init_local_schema
from app.main import app


@pytest.fixture
def planner_client(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "inbox-test.db"),
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    init_local_schema(engine)
    from app.planner import init_local_schema as planner_schema
    planner_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with session() as db:
            yield db

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), engine
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        engine.dispose()



def test_volley_metrics_require_opt_in_and_count_each_observation_once(planner_client, monkeypatch):
    c, _ = planner_client
    workout = c.post("/api/life/workouts", json={
        "name": "Allenamento", "day": "2026-11-26", "sport": "Pallavolo"
    }).json()["id"]
    path = f"/api/life/volley/{workout}/metrics"
    observation = {"id": str(uuid4()), "skill": "serve", "attempts": 10, "successful": 8}
    monkeypatch.delenv("NEXUS_VOLLEY_METRICS", raising=False)
    assert c.get("/api/life/volley/capabilities").json() == {"metrics": False}
    assert c.post(path, json=observation).status_code == 404
    monkeypatch.setenv("NEXUS_VOLLEY_METRICS", "1")
    assert c.get(path).json() == []
    expected = [{"skill": "serve", "attempts": 10, "successful": 8}]
    for _ in range(2):
        assert c.post(path, json=observation).json() == expected
    assert c.post(path, json={**observation, "successful": 9}).status_code == 409
    assert c.post(path, json={**observation, "successful": 11}).status_code == 422
    assert c.get(path).json() == expected
    another = c.post("/api/life/workouts", json={
        "name": "Corsa", "day": "2026-11-26", "sport": "Corsa"
    }).json()["id"]
    assert c.get(f"/api/life/volley/{another}/metrics").status_code == 404


def test_dependencies_reject_cycles_and_lost_updates(planner_client):
    c, _ = planner_client
    def put(key, dependencies, version=0):
        return c.put("/api/planner/placements/"+key,json={"dependencies":dependencies,"version":version,"energy":"alta","context":"scuola"})
    assert put("school-2", ["school-1"]).status_code == 200
    assert put("school-3", ["school-2"]).status_code == 200
    assert put("school-1", ["school-3"]).status_code == 422
    assert put("school-2", []).status_code == 409
    assert put("school-2", [],1).status_code == 200


def test_focus_notification_is_atomic_and_single(planner_client):
    c, _ = planner_client
    f=c.post("/api/planner/focus",json={"source_key":"school-1","target_minutes":5}).json()
    path="/api/planner/focus/"+str(f["id"])+"/complete"
    assert c.post(path).status_code == 200
    assert c.post(path).status_code == 409
    notices=c.get("/api/notifications").json()
    assert sum(n["title"]=="Sessione focus conclusa" for n in notices)==1


def test_calendar_deletion_removes_block_metadata(planner_client):
    c, engine = planner_client
    b=c.post("/api/planner/blocks",json={"title":"Studio","starts_at":"2026-11-19T17:00:00+01:00","ends_at":"2026-11-19T18:00:00+01:00"})
    assert b.status_code==201,b.text
    assert c.delete("/api/life/events/"+str(b.json()["event_id"])).status_code==204
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM planner_event_links").scalar_one()==0


def test_routine_order_preserves_completion(planner_client):
    c, _=planner_client
    rid=c.post("/api/life/routines",json={"name":"Sera"}).json()["id"]
    url=f"/api/life/routines/{rid}"
    a,b=[c.post(url+"/steps",json={"title":t,"duration_minutes":10}).json()["id"] for t in ("Leggi","Ripassa")]
    assert c.post(url+f"/complete?step_id={a}").status_code==200
    assert c.put(url+"/order",json={"expected":[a,b],"ordered":[b,b]}).status_code==422
    assert c.put(url+"/order",json={"expected":[a,b],"ordered":[b,a]}).status_code==204
    assert c.put(url+"/order",json={"expected":[a,b],"ordered":[a,b]}).status_code==409
    data=c.get("/api/life/routines").json()[0]
    assert [r["id"] for r in data["steps"]]==[b,a] and data["completed_steps"]==[a]

def test_assistant_sends_only_approved_context(planner_client, monkeypatch):
    import httpx
    from datetime import date
    c, _ = planner_client
    monkeypatch.setenv("NEXUS_AI_BASE_URL","https://provider.invalid/v1")
    monkeypatch.setenv("NEXUS_AI_MODEL","test-model")
    monkeypatch.setenv("NEXUS_DESKTOP_AI_ENABLED","1")
    sent=[]
    class Provider:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,headers,json):
            sent.append(json)
            return httpx.Response(200,request=httpx.Request("POST",url),json={"choices":[{"message":{"content":"Preparare il capitolo."}}]})
    monkeypatch.setattr(httpx,"AsyncClient",Provider)
    body={"consent":False,"day":date.today().isoformat(),"question":"Come mi organizzo?",
          "items":[{"title":"Preparare il capitolo","source":"Academic"}]}
    assert c.post("/api/planner/assistant",json=body).status_code==422 and not sent
    body["consent"]=True
    result=c.post("/api/planner/assistant",json=body)
    assert result.json()=={"answer":"Preparare il capitolo."}
    assert len(sent)==1 and sent[0]["model"]=="test-model"
    import json
    approved=json.loads(sent[0]["messages"][1]["content"])
    assert approved["items"]==[{"title":"Preparare il capitolo","source":"Academic","due":None}]
    assert c.get("/api/planner/days/"+body["day"]).json()["version"]==0
