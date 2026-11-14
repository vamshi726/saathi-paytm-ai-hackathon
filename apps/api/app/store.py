import json
from contextlib import contextmanager
from pathlib import Path

from app.database import get_connection
from app.models import Case, CaseStatus, Order, Payment, Refund

SEED_CASE = Case(
    id="CS-1043",
    tenant_id="demo-merchant",
    customer_ref="CUS-1043",
    order_ref="ORD-2043",
    message="I paid INR 899, but my order still says unpaid.",
)
SEED_ORDER = Order(
    id="ORD-2043",
    tenant_id="demo-merchant",
    customer_ref="CUS-1043",
    amount_minor=89900,
)
SEED_PAYMENT = Payment(
    id="TXN-1043",
    tenant_id="demo-merchant",
    customer_ref="CUS-1043",
    order_ref="ORD-2043",
    amount_minor=89900,
)


def fixtures():
    """Synthetic-only records backing the five demo paths and risk comparison."""
    items = [("case", SEED_CASE), ("order", SEED_ORDER), ("payment", SEED_PAYMENT)]
    cases = [
        Case(
            id="CS-1042",
            tenant_id="demo-merchant",
            customer_ref="CUS-1042",
            order_ref="ORD-2042",
            message="I was charged twice for my INR 1,299 order.",
            goal="duplicate_payment",
        ),
        Case(
            id="CS-1044",
            tenant_id="demo-merchant",
            customer_ref="CUS-1044",
            order_ref="ORD-2044",
            message="Where is my INR 2,450 refund?",
            goal="refund_status",
            status=CaseStatus.PENDING_EXTERNAL,
            risk_tier="GREEN",
            refund_ref="RF-1044",
            refund_status="PROCESSING",
            outcome="Your synthetic refund is PROCESSING. Bank credit has not been verified.",
        ),
        Case(
            id="CS-1045",
            tenant_id="demo-merchant",
            customer_ref="CUS-1045",
            order_ref="ORD-2045",
            message="Refund INR 25,000 to my alternate account.",
            goal="alternate_account",
            status=CaseStatus.ESCALATED,
            risk_tier="RED",
            evidence_refs=["INR 25,000", "alternate destination"],
            outcome="Alternate-account refund needs enhanced human review.",
        ),
        Case(
            id="CS-1046",
            tenant_id="demo-merchant",
            customer_ref="CUS-1046",
            order_ref="",
            message="I was charged twice. Refund one payment.",
            goal="clarification",
        ),
        Case(
            id="RISK-HISTORY-02",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            order_ref="ORD-RISK-02",
            message="I was charged twice for my INR 1,299 order. History variant.",
            goal="duplicate_payment",
        ),
    ]
    orders = [
        Order(
            id="ORD-2042",
            tenant_id="demo-merchant",
            customer_ref="CUS-1042",
            amount_minor=129900,
            status="PAID",
        ),
        Order(
            id="ORD-2044",
            tenant_id="demo-merchant",
            customer_ref="CUS-1044",
            amount_minor=245000,
            status="PAID",
        ),
        Order(
            id="ORD-2045",
            tenant_id="demo-merchant",
            customer_ref="CUS-1045",
            amount_minor=2500000,
            status="PAID",
        ),
        Order(
            id="ORD-2046",
            tenant_id="demo-merchant",
            customer_ref="CUS-1046",
            amount_minor=89900,
            status="PAID",
        ),
        Order(
            id="ORD-RISK-02",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            amount_minor=129900,
            status="PAID",
        ),
    ]
    payments = [
        Payment(
            id="TXN-42A",
            tenant_id="demo-merchant",
            customer_ref="CUS-1042",
            order_ref="ORD-2042",
            amount_minor=129900,
        ),
        Payment(
            id="TXN-42B",
            tenant_id="demo-merchant",
            customer_ref="CUS-1042",
            order_ref="ORD-2042",
            amount_minor=129900,
        ),
        Payment(
            id="TXN-46A",
            tenant_id="demo-merchant",
            customer_ref="CUS-1046",
            order_ref="ORD-2046",
            amount_minor=89900,
        ),
        Payment(
            id="TXN-46B",
            tenant_id="demo-merchant",
            customer_ref="CUS-1046",
            order_ref="ORD-2046",
            amount_minor=89900,
            status="PENDING_AUTHORIZATION",
        ),
        Payment(
            id="TXN-R1",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            order_ref="ORD-RISK-02",
            amount_minor=129900,
        ),
        Payment(
            id="TXN-R2",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            order_ref="ORD-RISK-02",
            amount_minor=129900,
        ),
    ]
    refunds = [
        Refund(
            id="RF-1044",
            tenant_id="demo-merchant",
            customer_ref="CUS-1044",
            order_ref="ORD-2044",
            source_transaction_ref="TXN-OLD-44",
            amount_minor=245000,
            status="PROCESSING",
        ),
        Refund(
            id="RF-H1",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            order_ref="ORD-OLD-1",
            source_transaction_ref="TXN-OLD-1",
            amount_minor=10000,
            status="SUCCEEDED",
        ),
        Refund(
            id="RF-H2",
            tenant_id="demo-merchant",
            customer_ref="CUS-RISK-02",
            order_ref="ORD-OLD-2",
            source_transaction_ref="TXN-OLD-2",
            amount_minor=10000,
            status="SUCCEEDED",
        ),
    ]
    items.extend(("case", x) for x in cases)
    items.extend(("order", x) for x in orders)
    items.extend(("payment", x) for x in payments)
    items.extend(("refund", x) for x in refunds)
    return items


class Store:
    def __init__(self, path: str, full_demo: bool = True):
        self.path = path
        self.full_demo = full_demo

    @contextmanager
    def connect(self, *, write=False):
        db = get_connection(self.path)
        try:
            if write:
                # Serialize runs across threads/processes, including the terminal-state check.
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, tenant_id TEXT NOT NULL, id TEXT NOT NULL,
                body TEXT NOT NULL, PRIMARY KEY (kind, tenant_id, id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL, case_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                stage TEXT NOT NULL, detail TEXT NOT NULL, action_id TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""")
            self._seed(db, ignore_existing=True)

    def _seed(self, db, *, ignore_existing: bool) -> None:
        seed_records = (
            fixtures()
            if self.full_demo
            else [("case", SEED_CASE), ("order", SEED_ORDER), ("payment", SEED_PAYMENT)]
        )
        statement = (
            "INSERT OR IGNORE INTO records VALUES (?, ?, ?, ?)"
            if ignore_existing
            else "INSERT INTO records VALUES (?, ?, ?, ?)"
        )
        for kind, record in seed_records:
            record_id = (
                getattr(record, "id", None)
                or getattr(record, "approval_id", None)
                or getattr(record, "message_id", None)
            )
            db.execute(statement, (kind, record.tenant_id, record_id, record.model_dump_json()))

    def reset_demo(self) -> None:
        """Clear local synthetic state and restore the initial fixture records."""
        with self.connect(write=True) as db:
            db.execute("DELETE FROM events")
            db.execute("DELETE FROM records")
            self._seed(db, ignore_existing=False)

    @staticmethod
    def get(db, kind, tenant_id, record_id):
        row = db.execute(
            "SELECT body FROM records WHERE kind=? AND tenant_id=? AND id=?",
            (kind, tenant_id, record_id),
        ).fetchone()
        return json.loads(row["body"]) if row else None

    @staticmethod
    def list(db, kind, tenant_id):
        rows = db.execute(
            "SELECT body FROM records WHERE kind=? AND tenant_id=? ORDER BY id",
            (kind, tenant_id),
        ).fetchall()
        return [json.loads(row["body"]) for row in rows]

    @staticmethod
    def save(db, kind, record):
        record_id = (
            getattr(record, "id", None)
            or getattr(record, "approval_id", None)
            or getattr(record, "message_id", None)
        )
        if not record_id:
            raise ValueError(f"No record id for {kind}")
        db.execute(
            """INSERT INTO records (kind, tenant_id, id, body) VALUES (?, ?, ?, ?)
               ON CONFLICT(kind, tenant_id, id) DO UPDATE SET body=excluded.body""",
            (kind, record.tenant_id, record_id, record.model_dump_json()),
        )

    @staticmethod
    def event(db, case, actor, stage, detail, action_id=None):
        db.execute(
            """INSERT INTO events (tenant_id, case_id, actor_id, stage, detail, action_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (case.tenant_id, case.id, actor.actor_id, stage, detail, action_id),
        )
