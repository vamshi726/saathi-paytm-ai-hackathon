import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import Actor, Case, Event
from app.store import Store
from app.workflow import run_case, visible_case

bearer = HTTPBearer(auto_error=False)


def create_app(db_path: str | None = None, demo_token: str | None = None) -> FastAPI:
    store = Store(db_path or os.getenv("SAATHI_DB_PATH", ".data/saathi.sqlite3"))
    token = demo_token if demo_token is not None else os.getenv("SAATHI_DEMO_TOKEN", "")

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        yield

    app = FastAPI(title="Saathi — synthetic support demo", version="0.1.0", lifespan=lifespan)
    app.state.store = store

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Actor:
        if not token or token == "replace-with-a-local-demo-token":
            raise HTTPException(503, "Configure SAATHI_DEMO_TOKEN to enable the local demo")
        if credentials is None or not secrets.compare_digest(credentials.credentials, token):
            raise HTTPException(
                401, "Valid demo bearer token required", headers={"WWW-Authenticate": "Bearer"}
            )
        # Identity is server-controlled; client headers cannot select a tenant or role.
        return Actor(actor_id="demo-support", tenant_id="demo-merchant", role="support")

    app.state.authenticate = authenticate

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "synthetic-deterministic"}

    @app.get("/api/session")
    def session(actor: Annotated[Actor, Depends(authenticate)]):
        # UI hints only: each action still enforces its own backend authorization.
        capabilities = ["metrics"]
        if actor.role in {"support", "supervisor"}:
            capabilities.append("run")
        return {
            **actor.model_dump(),
            "mode": "synthetic-deterministic",
            "capabilities": capabilities,
        }

    @app.get("/api/metrics")
    def metrics(actor: Annotated[Actor, Depends(authenticate)]):
        with store.connect() as db:
            records = [Case.model_validate(r) for r in Store.list(db, "case", actor.tenant_id)]
        return {
            "total_cases": len(records),
            "resolved_cases": sum(r.status == "RESOLVED" for r in records),
            "pending_cases": sum(r.status == "PENDING_EXTERNAL" for r in records),
            "escalated_cases": sum(r.status == "ESCALATED" for r in records),
            "approval_cases": sum(r.status == "NEEDS_APPROVAL" for r in records),
            "synthetic": True,
        }

    @app.get("/api/cases", response_model=list[Case])
    def cases(
        actor: Annotated[Actor, Depends(authenticate)],
        q: Annotated[str, Query(max_length=200)] = "",
    ):
        with store.connect() as db:
            records = [Case.model_validate(r) for r in Store.list(db, "case", actor.tenant_id)]
            return [
                r
                for r in records
                if q.casefold() in f"{r.id} {r.order_ref} {r.message} {r.status}".casefold()
            ]

    @app.get("/api/cases/{case_id}", response_model=Case)
    def case_detail(case_id: str, actor: Annotated[Actor, Depends(authenticate)]):
        with store.connect() as db:
            return visible_case(db, actor, case_id)

    @app.post("/api/cases/{case_id}/run", response_model=Case)
    def run(case_id: str, actor: Annotated[Actor, Depends(authenticate)]):
        return run_case(store, actor, case_id)

    @app.get("/api/cases/{case_id}/events", response_model=list[Event])
    def events(case_id: str, actor: Annotated[Actor, Depends(authenticate)]):
        with store.connect() as db:
            visible_case(db, actor, case_id)
            return [
                dict(row)
                for row in db.execute(
                    """SELECT sequence, case_id, actor_id, stage, detail, action_id, created_at
                   FROM events WHERE tenant_id=? AND case_id=? ORDER BY sequence""",
                    (actor.tenant_id, case_id),
                )
            ]

    return app


app = create_app()
