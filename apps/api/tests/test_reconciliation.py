from concurrent.futures import ThreadPoolExecutor

import pytest
from app.main import create_app
from app.models import Actor, Order, Payment
from app.store import Store
from app.workflow import run_case
from fastapi.testclient import TestClient

HEADERS = {"Authorization": "Bearer test-demo-token"}
ACTOR = Actor(actor_id="tester", tenant_id="demo-merchant", role="support")
RUN = "/api/cases/CS-1043/run"


@pytest.fixture
def setup(tmp_path):
    app = create_app(str(tmp_path / "test.sqlite3"), "test-demo-token")
    with TestClient(app) as client:
        yield app, client


def test_verified_closure_and_replay(setup):
    app, client = setup
    assert client.get("/api/cases", headers=HEADERS).json()[0]["status"] == "NEW"
    first = client.post(RUN, headers=HEADERS)
    assert first.status_code == 200
    assert first.json()["status"] == "RESOLVED"
    assert client.post(RUN, headers=HEADERS).json() == first.json()
    with app.state.store.connect() as db:
        assert Store.get(db, "order", ACTOR.tenant_id, "ORD-2043")["status"] == "PAID"
    events = client.get("/api/cases/CS-1043/events", headers=HEADERS).json()
    stages = [e["stage"] for e in events]
    assert stages.count("reconcile_order") == 1
    assert stages.index("reconcile_order") < stages.index("verify_order") < stages.index("resolved")
    assert all(e["actor_id"] == "demo-support" for e in events)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "PENDING_AUTHORIZATION"),
        ("status", "REFUNDED"),
        ("amount_minor", 1),
        ("currency", "USD"),
        ("customer_ref", "another-customer"),
    ],
)
def test_ineligible_payment_never_changes_order(setup, field, value):
    app, client = setup
    with app.state.store.connect(write=True) as db:
        record = Store.get(db, "payment", ACTOR.tenant_id, "TXN-1043")
        record[field] = value
        Store.save(db, "payment", Payment.model_validate(record))
    assert client.post(RUN, headers=HEADERS).json()["status"] == "ESCALATED"
    with app.state.store.connect() as db:
        assert Store.get(db, "order", ACTOR.tenant_id, "ORD-2043")["status"] == "UNPAID"
        count = db.execute("SELECT count(*) FROM events WHERE stage='reconcile_order'").fetchone()[
            0
        ]
        assert count == 0


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "other_tenant"])
def test_ambiguous_or_cross_tenant_evidence(setup, mutation):
    app, client = setup
    with app.state.store.connect(write=True) as db:
        if mutation == "missing":
            db.execute("DELETE FROM records WHERE kind='payment'")
        elif mutation == "other_tenant":
            db.execute("UPDATE records SET tenant_id='other' WHERE kind='payment'")
        else:
            record = Store.get(db, "payment", ACTOR.tenant_id, "TXN-1043")
            payment = Payment.model_validate(record)
            payment.id = "TXN-DUPLICATE"
            db.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?)",
                ("payment", payment.tenant_id, payment.id, payment.model_dump_json()),
            )
    assert client.post(RUN, headers=HEADERS).json()["status"] == "ESCALATED"


def test_failed_verification_does_not_close(setup, monkeypatch):
    _, client = setup
    from app import workflow

    original = workflow.read_order
    calls = 0

    def stale_read(db, case):
        nonlocal calls
        calls += 1
        order = original(db, case)
        if calls == 2:
            order.status = "UNPAID"
        return order

    monkeypatch.setattr(workflow, "read_order", stale_read)
    assert client.post(RUN, headers=HEADERS).json()["status"] == "ESCALATED"


def test_authentication_and_scope(setup):
    app, client = setup
    assert client.post(RUN).status_code == 401
    assert client.post(RUN, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/cases/missing", headers=HEADERS).status_code == 404
    app.dependency_overrides[app.state.authenticate] = lambda: Actor(
        actor_id="other", tenant_id="other-merchant", role="support"
    )
    assert client.get("/api/cases", headers=HEADERS).json() == []
    assert client.post(RUN, headers=HEADERS).status_code == 404
    assert client.get("/api/cases/CS-1043/events", headers=HEADERS).status_code == 404
    app.dependency_overrides[app.state.authenticate] = lambda: Actor(
        actor_id="customer", tenant_id="demo-merchant", role="customer"
    )
    assert client.post(RUN, headers=HEADERS).status_code == 403


def test_missing_configuration_fails_closed(tmp_path):
    with TestClient(create_app(str(tmp_path / "db.sqlite3"), "")) as client:
        assert client.get("/api/cases", headers=HEADERS).status_code == 503


def test_concurrent_runs_and_restart(setup):
    app, _ = setup
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_case(app.state.store, ACTOR, "CS-1043"), range(8)))
    assert all(r.status == "RESOLVED" for r in results)
    with TestClient(create_app(app.state.store.path, "test-demo-token")) as restarted:
        assert restarted.post(RUN, headers=HEADERS).json()["status"] == "RESOLVED"
        events = restarted.get("/api/cases/CS-1043/events", headers=HEADERS).json()
        assert sum(e["stage"] == "reconcile_order" for e in events) == 1


def test_search_and_invalid_order(setup):
    app, client = setup
    assert len(client.get("/api/cases?q=unpaid", headers=HEADERS).json()) == 1
    assert client.get("/api/cases?q=unknown", headers=HEADERS).json() == []
    with app.state.store.connect(write=True) as db:
        order = Order.model_validate(Store.get(db, "order", ACTOR.tenant_id, "ORD-2043"))
        order.status = "CANCELLED"
        Store.save(db, "order", order)
    assert client.post(RUN, headers=HEADERS).json()["status"] == "ESCALATED"


def test_exception_rolls_back_write_and_audit(setup, monkeypatch):
    app, client = setup
    from app import workflow

    original = workflow.read_order
    calls = 0

    def fail_verification(db, case):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TimeoutError("Simulated verification failure")
        return original(db, case)

    monkeypatch.setattr(workflow, "read_order", fail_verification)
    with pytest.raises(TimeoutError):
        client.post(RUN, headers=HEADERS)
    with app.state.store.connect() as db:
        assert Store.get(db, "order", ACTOR.tenant_id, "ORD-2043")["status"] == "UNPAID"
        assert Store.get(db, "case", ACTOR.tenant_id, "CS-1043")["status"] == "NEW"
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
