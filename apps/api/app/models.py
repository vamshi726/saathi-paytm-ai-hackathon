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


class Event(Record):
    sequence: int
    case_id: str
    actor_id: str
    stage: str
    detail: str
    action_id: str | None
    created_at: str
