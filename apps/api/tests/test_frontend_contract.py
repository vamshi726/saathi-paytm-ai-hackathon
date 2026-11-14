from app.models import Actor
from test_reconciliation import HEADERS, RUN, setup  # noqa: F401


def test_frontend_identity_and_metrics(setup):  # noqa: F811
    app, client = setup
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/metrics").status_code == 401
    identity = client.get("/api/session", headers=HEADERS).json()
    assert identity["role"] == "support"
    assert identity["capabilities"] == ["metrics", "run"]
    assert "approvals" not in identity["capabilities"]
    before = client.get("/api/metrics", headers=HEADERS).json()
    assert before["total_cases"] == 1
    assert before["resolved_cases"] == 0
    client.post(RUN, headers=HEADERS)
    after = client.get("/api/metrics", headers=HEADERS).json()
    assert after["resolved_cases"] == 1
    assert after["pending_cases"] == 0
    assert after["synthetic"] is True
    app.dependency_overrides[app.state.authenticate] = lambda: Actor(
        actor_id="other", tenant_id="other-merchant", role="customer"
    )
    assert client.get("/api/metrics", headers=HEADERS).json()["total_cases"] == 0
    assert client.get("/api/session", headers=HEADERS).json()["capabilities"] == ["metrics"]

