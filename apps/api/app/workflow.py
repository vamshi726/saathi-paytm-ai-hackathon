from fastapi import HTTPException

from app.models import Actor, Case, CaseStatus, Order, Payment
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
