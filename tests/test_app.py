import pytest

from app import create_app
from config import TestingConfig
from database.db import db
from extensions import bcrypt
from models.user import User


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        for name, email, role in [("Admin", "admin@test.io", "admin"),
                                  ("Eng", "eng@test.io", "engineer")]:
            db.session.add(User(
                name=name, email=email, role=role, is_active=True,
                password_hash=bcrypt.generate_password_hash("password123").decode()))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email="admin@test.io"):
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200


def make_incident(client, **extra):
    body = {"title": "API down", "service_name": "Payments", "description": "Timeouts",
            "severity": "high", "priority": "high"}
    body.update(extra)
    r = client.post("/api/incidents", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["incident"]["id"]


def test_health_endpoints(client):
    for path in ("/api/health", "/health"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.get_json()["data"]["status"] == "healthy"


def test_unknown_route_uses_standard_error_shape(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["success"] is False and "error" in r.get_json()


def test_pages_redirect_to_login_when_anonymous(client):
    r = client.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.get("/api/incidents").status_code == 401


def test_every_page_renders_when_logged_in(client):
    login(client)
    for path in ["/dashboard", "/incidents", "/incidents/create", "/incidents/1", "/ai-analysis",
                 "/ai-assistant", "/shift-handover", "/memory-explorer", "/settings", "/login"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200, path


def test_incident_lifecycle_and_trailing_slash(client):
    login(client)
    iid = make_incident(client)
    assert client.get("/api/incidents/?page=1&per_page=5").status_code == 200
    assert client.get("/api/incidents?search=api").get_json()["pagination"]["total"] == 1
    assert client.post("/api/incidents/%d/actions" % iid,
                       json={"action_description": "Restarted", "outcome": "failed"}).status_code == 201
    assert client.patch("/api/incidents/%d/status" % iid, json={"status": "investigating"}).status_code == 200
    r = client.post("/api/incidents/%d/resolve" % iid,
                    json={"resolution_summary": "Fixed pool", "verified_root_cause": "Pool exhausted"})
    assert r.status_code == 200
    stats = client.get("/api/incidents/stats").get_json()["stats"]
    assert stats["total"] == 1 and stats["resolved"] == 1 and stats["active"] == 0
    detail = client.get("/api/incidents/%d" % iid).get_json()["incident"]
    assert detail["actions"][0]["engineer_name"] == "Admin"


def test_delete_requires_admin_and_cascades(client):
    login(client)
    iid = make_incident(client)
    client.post("/api/incidents/%d/actions" % iid, json={"action_description": "x"})
    assert client.delete("/api/incidents/%d" % iid).status_code == 200
    login(client, "eng@test.io")
    iid = make_incident(client)
    assert client.delete("/api/incidents/%d" % iid).status_code == 403


def test_registration_is_admin_only_by_default(app):
    app.config["ALLOW_PUBLIC_REGISTRATION"] = False
    c = app.test_client()
    body = {"name": "New", "email": "new@test.io", "password": "password123"}
    assert c.post("/api/auth/register", json=body).status_code == 401
    login(c, "eng@test.io")
    assert c.post("/api/auth/register", json=body).status_code == 403
    login(c)
    assert c.post("/api/auth/register", json=body).status_code == 201


def test_change_password(client):
    login(client)
    r = client.post("/api/auth/change-password",
                    json={"current_password": "password123", "new_password": "newpassword9"})
    assert r.status_code == 200
    assert client.post("/api/auth/change-password",
                       json={"current_password": "wrong", "new_password": "newpassword9"}).status_code == 400


def test_ai_endpoints_report_missing_keys_cleanly(client):
    login(client)
    iid = make_incident(client)
    st = client.get("/api/ai/status").get_json()
    assert st["groq"]["configured"] is False and st["hindsight"]["configured"] is False
    assert client.post("/api/ai/analyze", json={"incident_id": iid}).status_code == 503
    assert client.post("/api/ai/chat", json={"message": "hi"}).status_code == 503
    assert client.post("/api/memory/search", json={"query": "x"}).status_code == 503


def test_handover_works_without_ai_and_exports_pdf(client):
    login(client)
    make_incident(client)
    r = client.post("/api/handovers", json={"shift_hours": 8, "notes": "Watch DB"})
    assert r.status_code == 201
    h = r.get_json()["handover"]
    assert h["ai_generated"] is False and len(h["active_incidents"]) == 1
    pdf = client.get("/api/handovers/%d/pdf" % h["id"])
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    assert client.get("/api/handovers").get_json()["data"][0]["id"] == h["id"]


def test_ai_analysis_with_mocked_groq(app, client, monkeypatch):
    from services import ai_service
    monkeypatch.setitem(app.config, "GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: (
        '{"summary":"s","probable_causes":[{"cause":"pool","likelihood":"high","reasoning":"r"}],'
        '"recommended_steps":["a"],"things_to_verify":["b"],"escalation_advice":"e"}'))
    login(client)
    iid = make_incident(client)
    r = client.post("/api/ai/analyze", json={"incident_id": iid})
    assert r.status_code == 200
    assert r.get_json()["analysis"]["probable_causes"][0]["cause"] == "pool"
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: "Try checking the pool.")
    c = client.post("/api/ai/chat", json={"message": "help"}).get_json()
    assert c["reply"].startswith("Try") and client.get("/api/ai/chat/sessions").get_json()["data"]


def test_csrf_is_enforced_when_enabled():
    from config import TestingConfig as T

    class Csrf(T):
        WTF_CSRF_ENABLED = True

    app = create_app(Csrf)
    with app.app_context():
        db.create_all()
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "a@b.co", "password": "x"})
    assert r.status_code == 400 and "Security token" in r.get_json()["message"]
    token = c.get("/api/auth/csrf").get_json()["csrf_token"]
    r = c.post("/api/auth/login", json={"email": "a@b.co", "password": "x"},
               headers={"X-CSRFToken": token})
    assert r.status_code == 401


def test_email_otp_full_workflow(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "OTP_ENABLED_IN_TESTING", True)
    captured = []
    import routes.auth_routes as auth
    monkeypatch.setattr(auth, "send_otp_email", lambda email, name, code: captured.append(code))

    # 1. Login with correct password generates an OTP challenge
    r = client.post("/api/auth/login", json={"email": "admin@test.io", "password": "password123"})
    assert r.status_code == 200
    assert r.get_json()["otp_required"] is True
    assert len(captured) == 1
    otp = captured[0]

    # Client is NOT authenticated before OTP
    assert client.get("/api/auth/me").status_code == 401

    # 2. Invalid OTP format fails
    r_bad = client.post("/api/auth/verify-otp", json={"otp": "123"})
    assert r_bad.status_code == 400

    # 3. Incorrect OTP fails
    r_wrong = client.post("/api/auth/verify-otp", json={"otp": "999999" if otp != "999999" else "000000"})
    assert r_wrong.status_code == 401

    # 4. Correct OTP verifies and authenticates
    r_ok = client.post("/api/auth/verify-otp", json={"otp": otp})
    assert r_ok.status_code == 200
    assert r_ok.get_json()["redirect"] == "/dashboard"

    # 5. User is now authenticated
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "admin@test.io"
