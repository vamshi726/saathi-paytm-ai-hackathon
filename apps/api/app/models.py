from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CaseStatus(StrEnum):
    NEW = "NEW"
    NEEDS_CUSTOMER_INFO = "NEEDS_CUSTOMER_INFO"
    INVESTIGATING = "INVESTIGATING"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    ACTION_RUNNING = "ACTION_RUNNING"
    PENDING_EXTERNAL = "PENDING_EXTERNAL"
    VERIFYING = "VERIFYING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Actor(Record):
    actor_id: str
    tenant_id: str
    role: str


class Case(Record):
    id: str
    tenant_id: str
    customer_ref: str
    order_ref: str
    message: str
    goal: str = "order_payment_verified"
    status: CaseStatus = CaseStatus.NEW
    outcome: str | None = None
    synthetic: bool = True
    risk_tier: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    reflection_revisions: int = 0
    refund_ref: str | None = None
    refund_status: str | None = None


class Order(Record):
    id: str
    tenant_id: str
    customer_ref: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    status: str = "UNPAID"


class Payment(Record):
    id: str
    tenant_id: str
    customer_ref: str
    order_ref: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    status: str = "CAPTURED"


class Refund(Record):
    id: str
    tenant_id: str
    customer_ref: str
    order_ref: str
    source_transaction_ref: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    status: str = "INITIATED"


class Approval(Record):
    approval_id: str
    tenant_id: str
    case_id: str
    action_id: str
    proposed_action: str = "initiate_mock_refund"
    source_transaction_ref: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    decision: str = "REQUESTED"
    expires_at: str
    payload_hash: str
    reviewer_ref: str | None = None
    reviewer_comment: str | None = None


class Message(Record):
    message_id: str
    tenant_id: str
    case_id: str
    sender: str
    text_redacted: str
    timestamp: str


class ApprovalDecision(Record):
    decision: str
    payload_hash: str
    comment: str = Field(min_length=1, max_length=1000)


class CustomerReply(Record):
    text: str = Field(min_length=1, max_length=2000)


class Event(Record):
    sequence: int
    case_id: str
    actor_id: str
    stage: str
    detail: str
    action_id: str | None
    created_at: str
