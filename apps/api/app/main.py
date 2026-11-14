import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.database import database_path
from app.models import (
    Actor,
    Approval,
    ApprovalDecision,
    Case,
    CaseStatus,
    CustomerReply,
    Event,
    Message,
    Refund,
)
from app.store import Store
from app.workflow import add_message, now, resume_customer_reply, run_case, visible_case


def create_app(db_path: str | None = None, demo_token: str | None = None) -> FastAPI:
    # Explicit paths are used by the compact legacy reconciliation test fixture.
    # The running app seeds the complete synthetic demo suite.
    store = Store(
        db_path or database_path(),
        full_demo=db_path is None or os.getenv("SAATHI_FULL_DEMO") == "1",
    )

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        yield

    app = FastAPI(title="Saathi — synthetic support demo", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = store

    def demo_actor() -> Actor:
        """Open, local-only demo identity. This endpoint has no authentication."""
        return Actor(actor_id="local-demo", tenant_id="demo-merchant", role="supervisor")

    app.state.demo_actor = demo_actor

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "synthetic-deterministic"}

    @app.get("/api/session")
    def session(actor: Annotated[Actor, Depends(demo_actor)]):
        capabilities = ["metrics"]
        if actor.role in {"support", "supervisor"}:
            capabilities.append("run")
        if actor.role == "supervisor":
            capabilities.extend(
                ["messages", "approvals", "settle", "inject_timeout", "evaluations", "reset"]
            )
        return {
            **actor.model_dump(),
            "mode": "synthetic-deterministic",
            "capabilities": capabilities,
        }

    @app.get("/api/metrics")
    def metrics(actor: Annotated[Actor, Depends(demo_actor)]):
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
        actor: Annotated[Actor, Depends(demo_actor)],
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
    def case_detail(case_id: str, actor: Annotated[Actor, Depends(demo_actor)]):
        with store.connect() as db:
            return visible_case(db, actor, case_id)

    @app.post("/api/cases/{case_id}/run", response_model=Case)
    def run(case_id: str, actor: Annotated[Actor, Depends(demo_actor)]):
        return run_case(store, actor, case_id)

    @app.get("/api/cases/{case_id}/events", response_model=list[Event])
    def events(case_id: str, actor: Annotated[Actor, Depends(demo_actor)]):
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

    @app.get("/api/cases/{case_id}/messages", response_model=list[Message])
    def messages(case_id: str, actor: Annotated[Actor, Depends(demo_actor)]):
        with store.connect() as db:
            visible_case(db, actor, case_id)
            return [
                Message.model_validate(r)
                for r in Store.list(db, "message", actor.tenant_id)
                if r["case_id"] == case_id
            ]

    @app.post("/api/cases/{case_id}/messages", response_model=Case)
    def customer_reply(
        case_id: str, payload: CustomerReply, actor: Annotated[Actor, Depends(demo_actor)]
    ):
        if actor.role not in {"support", "supervisor"}:
            raise HTTPException(403, "Support role required")
        return resume_customer_reply(store, actor, case_id, payload.text)

    @app.get("/api/approvals", response_model=list[Approval])
    def approvals(actor: Annotated[Actor, Depends(demo_actor)]):
        if actor.role != "supervisor":
            raise HTTPException(403, "Supervisor role required")
        with store.connect() as db:
            records = [
                Approval.model_validate(x) for x in Store.list(db, "approval", actor.tenant_id)
            ]
            return sorted(records, key=lambda x: x.expires_at)

    @app.post("/api/approvals/{approval_id}/decision")
    def decide_approval(
        approval_id: str, payload: ApprovalDecision, actor: Annotated[Actor, Depends(demo_actor)]
    ):
        if actor.role != "supervisor":
            raise HTTPException(403, "Supervisor role required")
        if payload.decision not in {"APPROVED", "REJECTED"}:
            raise HTTPException(422, "Decision must be APPROVED or REJECTED")
        with store.connect(write=True) as db:
            raw = Store.get(db, "approval", actor.tenant_id, approval_id)
            if not raw:
                raise HTTPException(404, "Approval not found")
            approval = Approval.model_validate(raw)
            case = visible_case(db, actor, approval.case_id)
            if (
                approval.decision != "REQUESTED"
                or approval.payload_hash != payload.payload_hash
                or approval.expires_at <= now()
            ):
                raise HTTPException(409, "Approval has changed or expired")
            approval.decision, approval.reviewer_ref = payload.decision, actor.actor_id
            approval.reviewer_comment = payload.comment.strip()
            Store.save(db, "approval", approval)
            Store.event(
                db,
                case,
                actor,
                "approval_decided",
                f"Supervisor {payload.decision.lower()} with comment: {approval.reviewer_comment}",
                approval.action_id,
            )
            if payload.decision == "REJECTED":
                case.status, case.outcome = (
                    CaseStatus.ESCALATED,
                    "Refund proposal rejected; human support will review this case.",
                )
                Store.event(db, case, actor, "approval_rejected", case.outcome, approval.action_id)
                add_message(db, case, "assistant", case.outcome)
            else:
                # Revalidate exact action from server-side evidence before mock write.
                payments = [
                    p
                    for p in Store.list(db, "payment", actor.tenant_id)
                    if p["id"] == approval.source_transaction_ref
                ]
                if len(payments) != 1 or payments[0]["amount_minor"] != approval.amount_minor:
                    raise HTTPException(409, "Approval evidence no longer validates")
                refund = Refund(
                    id=f"RF-{case.id}",
                    tenant_id=case.tenant_id,
                    customer_ref=case.customer_ref,
                    order_ref=case.order_ref,
                    source_transaction_ref=approval.source_transaction_ref,
                    amount_minor=approval.amount_minor,
                )
                Store.save(db, "refund", refund)
                case.status, case.refund_ref, case.refund_status = (
                    CaseStatus.PENDING_EXTERNAL,
                    refund.id,
                    refund.status,
                )
                Store.event(
                    db,
                    case,
                    actor,
                    "initiate_mock_refund",
                    "Mock refund initiated from the exact approved transaction.",
                    approval.action_id,
                )
                refund.status = "PROCESSING"
                Store.save(db, "refund", refund)
                case.refund_status = refund.status
                Store.event(
                    db,
                    case,
                    actor,
                    "process_mock_refund",
                    "Mock refund is processing.",
                    approval.action_id,
                )
                refund.status = "SUCCEEDED"
                Store.save(db, "refund", refund)
                case.status, case.refund_status = CaseStatus.RESOLVED, refund.status
                case.outcome = "Mock refund completed successfully."
                Store.event(
                    db,
                    case,
                    actor,
                    "verify_refund",
                    "Mock refund success was independently read back.",
                    approval.action_id,
                )
            Store.save(db, "case", case)
        return {"ok": True}

    @app.post("/api/mock/refunds/{refund_id}/settle")
    def settle(refund_id: str, actor: Annotated[Actor, Depends(demo_actor)]):
        if actor.role != "supervisor":
            raise HTTPException(403, "Supervisor role required")
        with store.connect(write=True) as db:
            raw = Store.get(db, "refund", actor.tenant_id, refund_id)
            if not raw:
                raise HTTPException(404, "Refund not found")
            refund = Refund.model_validate(raw)
            refund.status = "SUCCEEDED"
            Store.save(db, "refund", refund)
            candidates = [
                Case.model_validate(x)
                for x in Store.list(db, "case", actor.tenant_id)
                if x.get("refund_ref") == refund_id
            ]
            for case in candidates:
                case.status, case.refund_status = CaseStatus.RESOLVED, "SUCCEEDED"
                case.outcome = (
                    "Synthetic refund settlement was independently verified. No real funds moved."
                )
                Store.event(
                    db, case, actor, "verify_refund", "Mock settlement read-back: SUCCEEDED."
                )
                add_message(db, case, "assistant", case.outcome)
                Store.save(db, "case", case)
        return {"ok": True}

    @app.get("/api/evaluations/latest")
    def latest_evaluation(actor: Annotated[Actor, Depends(demo_actor)]):
        return None

    @app.post("/api/demo/reset")
    def reset_demo(actor: Annotated[Actor, Depends(demo_actor)]):
        """Reset all persisted synthetic conversations and workflow state."""
        store.reset_demo()
        return {"ok": True, "message": "Local demo reset to initial cases."}

    return app


app = create_app()
