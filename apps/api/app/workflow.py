from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from app.ai import advisory_plan
from app.models import Actor, Approval, Case, CaseStatus, Message, Order, Payment, Refund
from app.store import Store


def visible_case(db, actor: Actor, case_id: str) -> Case:
    record = Store.get(db, "case", actor.tenant_id, case_id)
    if record is None:
        raise HTTPException(404, "Case not found")
    return Case.model_validate(record)


def read_order(db, case: Case) -> Order | None:
    record = Store.get(db, "order", case.tenant_id, case.order_ref)
    return Order.model_validate(record) if record else None


def eligibility(case: Case, order: Order | None, payments: list[Payment]) -> str | None:
    if order is None or order.customer_ref != case.customer_ref:
        return "Order evidence is missing or belongs to a different customer."
    if order.status not in {"UNPAID", "PAID"}:
        return "Order state is not eligible for reconciliation."
    # Ambiguity, pending authorizations, duplicate captures and refunds need later workflows.
    if len(payments) != 1:
        return "Expected exactly one payment; conflicting or missing evidence needs review."
    payment = payments[0]
    if (
        payment.status != "CAPTURED"
        or payment.customer_ref != case.customer_ref
        or payment.amount_minor != order.amount_minor
        or payment.currency != order.currency
    ):
        return "Payment is not an exact captured match for this customer and order."
    return None


def run_case(store: Store, actor: Actor, case_id: str) -> Case:
    if actor.role not in {"support", "supervisor"}:
        raise HTTPException(403, "Support role required")
    # All local mock mutations and audit entries commit atomically. No remote writes occur.
    with store.connect(write=True) as db:
        case = visible_case(db, actor, case_id)
        if case.status in {CaseStatus.RESOLVED, CaseStatus.ESCALATED}:
            return case
        if case.status != CaseStatus.NEW:
            raise HTTPException(409, "Case is not ready to run")
        if case.id != "CS-1043":
            return run_extended_case(db, case, actor)
        case.status = CaseStatus.INVESTIGATING
        Store.event(db, case, actor, "triage", "Investigating payment/order mismatch.")
        order = read_order(db, case)
        Store.event(db, case, actor, "get_order", "Scoped order lookup completed.")
        payments = [
            Payment.model_validate(p)
            for p in Store.list(db, "payment", actor.tenant_id)
            if p["order_ref"] == case.order_ref
        ]
        Store.event(
            db,
            case,
            actor,
            "get_transaction",
            f"Scoped payment evidence: {', '.join(p.id for p in payments) or 'none'}.",
        )
        denied = eligibility(case, order, payments)
        if denied:
            case.status = CaseStatus.ESCALATED
            case.outcome = denied
            Store.event(db, case, actor, "policy_denied", denied)
        else:
            Store.event(db, case, actor, "policy_allowed", "GREEN: exact captured payment match.")
            case.status = CaseStatus.ACTION_RUNNING
            action_id = f"{case.id}:reconcile:{case.order_ref}"
            if order.status != "PAID":
                order.status = "PAID"
                Store.save(db, "order", order)
                Store.event(
                    db,
                    case,
                    actor,
                    "reconcile_order",
                    "Mock order changed to PAID; no funds moved.",
                    action_id,
                )
            case.status = CaseStatus.VERIFYING
            observed = read_order(db, case)
            Store.event(
                db, case, actor, "verify_order", "Independent order read-back completed.", action_id
            )
            if observed and observed.status == "PAID" and not eligibility(case, observed, payments):
                case.status = CaseStatus.RESOLVED
                case.outcome = "Your payment is confirmed and your mock order is now PAID."
            else:
                case.status = CaseStatus.ESCALATED
                case.outcome = "Order update could not be verified; human review is required."
            Store.event(db, case, actor, case.status.value.lower(), case.outcome, action_id)
        Store.save(db, "case", case)
        return case


def now() -> str:
    return datetime.now(UTC).isoformat()


def add_message(db, case: Case, sender: str, text: str) -> None:
    Store.save(
        db,
        "message",
        Message(
            message_id=str(uuid4()),
            tenant_id=case.tenant_id,
            case_id=case.id,
            sender=sender,
            text_redacted=text,
            timestamp=now(),
        ),
    )


def hash_approval(case: Case, action_id: str, source: str, amount: int) -> str:
    return sha256(
        f"{case.tenant_id}|{case.id}|{action_id}|{source}|{amount}|INR".encode()
    ).hexdigest()


def run_extended_case(db, case: Case, actor: Actor) -> Case:
    """Deterministic, auditable implementation of the same bounded graph used in demo mode.

    The planner is advisory; this function owns all policy and mock writes.
    """
    Store.event(
        db,
        case,
        actor,
        "context_specialist",
        "Classified synthetic request and assembled scoped evidence.",
    )
    suggestion = advisory_plan(case.id, case.message)
    if suggestion:
        Store.event(
            db,
            case,
            actor,
            "ai_advisory",
            "GPT-5 mini advisory received; server policy remains authoritative.",
        )
    if case.id == "CS-1046":
        case.status = CaseStatus.NEEDS_CUSTOMER_INFO
        case.outcome = "Please share your order ID so I can verify the transactions."
        Store.event(
            db,
            case,
            actor,
            "clarification_requested",
            "Order reference missing; no financial action considered.",
        )
        add_message(db, case, "assistant", case.outcome)
    elif case.id == "CS-1045":
        case.status, case.risk_tier = CaseStatus.ESCALATED, "RED"
        case.evidence_refs = ["INR 25,000", "alternate destination"]
        case.outcome = (
            "Alternate-account, high-value refund is blocked for enhanced human review. "
            "No refund was initiated."
        )
        Store.event(db, case, actor, "policy_denied", case.outcome)
        add_message(db, case, "assistant", case.outcome)
    elif case.id == "CS-1044":
        refund = next(
            (
                Refund.model_validate(r)
                for r in Store.list(db, "refund", case.tenant_id)
                if r["id"] == "RF-1044"
            ),
            None,
        )
        case.status, case.risk_tier = CaseStatus.PENDING_EXTERNAL, "GREEN"
        case.refund_ref, case.refund_status = "RF-1044", refund.status if refund else "UNKNOWN"
        case.outcome = "Your synthetic refund is PROCESSING. Bank credit has not been verified."
        Store.event(
            db, case, actor, "get_refund_status", "Read-only refund status lookup: PROCESSING."
        )
        add_message(db, case, "assistant", case.outcome)
    else:  # duplicate payment and the refund-history variant
        payments = [
            Payment.model_validate(p)
            for p in Store.list(db, "payment", case.tenant_id)
            if p["order_ref"] == case.order_ref and p["status"] == "CAPTURED"
        ]
        prior = [
            Refund.model_validate(r)
            for r in Store.list(db, "refund", case.tenant_id)
            if r["customer_ref"] == case.customer_ref
            and r["status"] in {"INITIATED", "PROCESSING", "SUCCEEDED"}
        ]
        case.evidence_refs = [p.id for p in payments] + [r.id for r in prior]
        if len(payments) != 2:
            case.status, case.risk_tier = CaseStatus.ESCALATED, "RED"
            case.outcome = "Conflicting payment evidence needs human review."
            Store.event(db, case, actor, "policy_denied", case.outcome)
        elif len(prior) >= 2:
            case.status, case.risk_tier = CaseStatus.ESCALATED, "RED"
            case.outcome = (
                "Two prior scoped refunds trigger enhanced review; "
                "no ordinary approval or refund is allowed."
            )
            Store.event(db, case, actor, "policy_denied", case.outcome)
        else:
            case.status, case.risk_tier = CaseStatus.NEEDS_APPROVAL, "AMBER"
            action_id, source = f"ACT-{case.id}-REFUND", payments[1].id
            digest = hash_approval(case, action_id, source, payments[1].amount_minor)
            approval = Approval(
                approval_id=f"APR-{case.id}",
                tenant_id=case.tenant_id,
                case_id=case.id,
                action_id=action_id,
                source_transaction_ref=source,
                amount_minor=payments[1].amount_minor,
                reason=(
                    f"Two captured payments for one order; {len(prior)} "
                    "prior refunds in scoped history."
                ),
                evidence_refs=case.evidence_refs,
                expires_at=(datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                payload_hash=digest,
            )
            Store.save(db, "approval", approval)
            case.outcome = (
                "A proposed mock refund is awaiting supervisor review. "
                "No refund has been initiated."
            )
            Store.event(
                db,
                case,
                actor,
                "approval_requested",
                "Exact mock refund proposal created; approval is required before any write.",
                action_id,
            )
        add_message(db, case, "assistant", case.outcome)
    Store.save(db, "case", case)
    return case


def resume_customer_reply(store: Store, actor: Actor, case_id: str, text: str) -> Case:
    with store.connect(write=True) as db:
        case = visible_case(db, actor, case_id)
        if case.status != CaseStatus.NEEDS_CUSTOMER_INFO:
            raise HTTPException(409, "Case is not waiting for customer information")
        add_message(db, case, "customer", text)
        if text.strip().upper() != "ORD-2046":
            case.outcome = "Please share the order ID. For this synthetic demo, use ORD-2046."
            add_message(db, case, "assistant", case.outcome)
            Store.event(
                db,
                case,
                actor,
                "clarification_invalid",
                "Customer reply did not provide a matching synthetic order ID.",
            )
        else:
            case.order_ref, case.status, case.risk_tier = "ORD-2046", CaseStatus.RESOLVED, "GREEN"
            case.evidence_refs = ["TXN-46A: CAPTURED", "TXN-46B: PENDING_AUTHORIZATION"]
            case.outcome = (
                "One completed charge is confirmed; the other is a pending authorization, "
                "so no refund was initiated."
            )
            Store.event(
                db,
                case,
                actor,
                "payment_resolver",
                "One CAPTURED and one PENDING_AUTHORIZATION payment found.",
            )
            Store.event(
                db,
                case,
                actor,
                "verification_specialist",
                "Evidence-backed explanation verified; no financial write requested.",
            )
            add_message(db, case, "assistant", case.outcome)
        Store.save(db, "case", case)
        return case
