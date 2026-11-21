from datetime import date

from app.ticktick import normalize

P = {"id": "p1", "name": "Scuola", "color": "#ffffff"}


def test_due_date_converted_to_local_day_and_overdue():
    t = {"id": "t1", "title": "Studiare", "priority": 5, "dueDate": "2026-11-14T23:00:00+0000"}
    n = normalize(t, P, date(2026, 11, 16))
    assert n["due_date"] == "2026-11-15" and n["overdue"] is True


def test_task_without_due_date():
    n = normalize({"id": "t2", "title": "Idea"}, P, date(2026, 11, 15))
    assert n["due_date"] is None and n["overdue"] is False and n["priority"] == 0


def test_due_date_with_milliseconds():
    t = {"id": "t3", "title": "Verifica", "dueDate": "2026-12-01T10:15:00.000+0000"}
    n = normalize(t, P, date(2026, 11, 16))
    assert n["due_date"] == "2026-12-01" and n["overdue"] is False


def test_unreadable_date_does_not_break():
    n = normalize({"id": "t4", "title": "X", "dueDate": "boh"}, P, date(2026, 11, 16))
    assert n["due_date"] is None


def test_cross_project_reconciliation_and_outage(tmp_path,monkeypatch):
    import httpx
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    from app import ticktick as tt
    engine=create_engine("sqlite:///"+str(tmp_path/"tick.db"))
    tt.IntegrationToken.__table__.create(engine)
    tt.TickSnapshot.__table__.create(engine)
    monkeypatch.setenv("TICKTICK_TOKEN","test-only")
    rows=[{"id":"same","projectId":"p1","title":"Originale","status":0}]
    inbox={"id":"other","projectId":"inbox123","title":"Senza data"}
    finished=[]
    def upstream(token, method, path, **kw):
        if path=="/project": return [{"id":"p1","name":"Scuola","kind":None}]
        if path=="/project/p1/data": return {"tasks":rows.copy()}
        if path=="/task/completed":return finished.copy()
        if path=="/task/filter":return rows+[inbox]
        raise AssertionError(path)
    monkeypatch.setattr(tt,"_req",upstream)
    with Session(engine) as db:
        first=tt.list_tasks(db)
        assert len(first["tasks"])==2 and not first["warnings"]
        rows[0]["title"]="Modificata"
        assert "Modificata" in [r["title"] for r in tt.list_tasks(db)["tasks"]]
        finished.append(rows.pop())
        final=tt.list_tasks(db)
        assert len(final["tasks"])==1 and final["completed"][0]["title"]=="Modificata"
    def outage(*args,**kw): raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(tt,"_req",outage)
    with Session(engine) as other:
        cached=tt.list_tasks(other)
        assert cached["tasks"]==final["tasks"] and cached["warnings"]


def test_remote_rename_compares_before_write(monkeypatch):
    from app import ticktick as tt
    from fastapi import HTTPException
    import pytest
    row={"id":"1","projectId":"p","title":"Prima","content":"Conserva","etag":"a"}
    writes=[]
    def api(token,method,path,**kw):
        if method=="GET":return row.copy()
        writes.append(kw["json"])
    monkeypatch.setattr(tt,"_req",api)
    monkeypatch.setattr(tt,"_token",lambda db:"test")
    req=tt.RenameTask(title="Dopo",revision=tt.fingerprint(row))
    tt.rename_task("p","1",req,None)
    assert writes==[{**row,"title":"Dopo"}]
    row["etag"]="b"
    with pytest.raises(HTTPException) as error:tt.rename_task("p","1",req,None)
    assert error.value.status_code==409 and len(writes)==1


def test_real_http_roundtrip_to_local_provider(tmp_path,monkeypatch):
    import json, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import ticktick as tt
    store={}
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,body):
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(body).encode())
        def do_GET(self):
            assert self.headers["Authorization"]=="Bearer test-only"
            self.send([{"id":"p","name":"Scuola"}] if self.path=="/project" else {"tasks":[r for r in store.values() if not r["status"]]})
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or "{}")
            if self.path=="/task":
                store["1"]={**data,"id":"1","status":0};self.send(store["1"])
            elif self.path.endswith("/complete"):
                store["1"]["status"]=2;self.send({})
            else:self.send([r for r in store.values() if bool(r["status"])==(self.path=="/task/completed")])
    server=ThreadingHTTPServer(("127.0.0.1",0),Provider)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(tt,"API",f"http://127.0.0.1:{server.server_port}")
    import os
    for key in list(os.environ):
        if key.lower() in {"http_proxy","https_proxy","all_proxy"}: monkeypatch.delenv(key)
    monkeypatch.setenv("NO_PROXY","127.0.0.1");monkeypatch.setenv("TICKTICK_TOKEN","test-only")
    engine=create_engine("sqlite:///"+str(tmp_path/"sync.db"))
    tt.IntegrationToken.__table__.create(engine);tt.TickSnapshot.__table__.create(engine)
    try:
        with Session(engine) as db:
            tt.create_task(tt.TaskIn(title="Test HTTP",project_id="p"),db)
            assert [t["title"] for t in tt.list_tasks(db)["tasks"]]==["Test HTTP"]
            store["1"]["title"]="Modifica alla fonte"
            assert tt.list_tasks(db)["tasks"][0]["title"]=="Modifica alla fonte"
            tt.complete_task("p","1",db)
            result=tt.list_tasks(db)
            assert not result["tasks"] and result["completed"][0]["id"]=="1"
    finally:
        server.shutdown();server.server_close();thread.join()


def test_oauth_state_survives_new_session_and_cannot_replay(tmp_path,monkeypatch):
    from urllib.parse import urlparse,parse_qs
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import ticktick as tt
    engine=create_engine("sqlite:///"+str(tmp_path/"oauth.db"))
    tt.IntegrationToken.__table__.create(engine)
    monkeypatch.setenv("TICKTICK_CLIENT_ID","test-client")
    monkeypatch.setenv("TICKTICK_TOKEN","older-test-value")
    with Session(engine) as first:
        state=parse_qs(urlparse(tt.login(first).headers["location"]).query)["state"][0]
    import httpx
    monkeypatch.setattr(httpx,"post",lambda *a,**kw:httpx.Response(200,json={"access_token":"new-test-value"}))
    with Session(engine) as second:
        assert "ticktick=errore" in tt.callback("code","wrong",second).headers["location"]
        assert "ticktick=ok" in tt.callback("code",state,second).headers["location"]
        assert tt._token(second)=="new-test-value"
        assert "ticktick=errore" in tt.callback("code",state,second).headers["location"]
