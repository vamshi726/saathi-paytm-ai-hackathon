import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.models import Case, Order, Payment

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


class Store:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
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
            for kind, record in [
                ("case", SEED_CASE),
                ("order", SEED_ORDER),
                ("payment", SEED_PAYMENT),
            ]:
                db.execute(
                    "INSERT OR IGNORE INTO records VALUES (?, ?, ?, ?)",
                    (kind, record.tenant_id, record.id, record.model_dump_json()),
                )

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
        db.execute(
            "UPDATE records SET body=? WHERE kind=? AND tenant_id=? AND id=?",
            (record.model_dump_json(), kind, record.tenant_id, record.id),
        )

    @staticmethod
    def event(db, case, actor, stage, detail, action_id=None):
        db.execute(
            """INSERT INTO events (tenant_id, case_id, actor_id, stage, detail, action_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (case.tenant_id, case.id, actor.actor_id, stage, detail, action_id),
        )
