from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token_claims
from app.models import Base
from app.models.user import User
from app.models.role import Role


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(username="tester", email="tester@example.com", full_name="Tester",
                    password_hash="test-hash", active_session_id="old-session",
                    session_last_activity_at=datetime.now(timezone.utc), is_active=True))
        db.commit()
    monkeypatch.setattr(auth, "verify_password", lambda plain, hashed: plain == "correct" and hashed == "test-hash")
    app = FastAPI()
    app.include_router(auth.router)
    def database():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def sign_in(client, password="correct", replace=False):
    return client.post("/auth/login", data={"username": "tester", "password": password,
                                           "replace_session": str(replace).lower()})


def test_active_session_requires_explicit_recovery(setup):
    client, engine = setup
    assert sign_in(client).status_code == 409
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == "old-session"


def test_recovery_replaces_session_and_old_token_cannot_access_or_logout(setup):
    client, engine = setup
    old_headers = {"Authorization": f"Bearer {create_access_token('tester', 'old-session')}"}
    response = sign_in(client, replace=True)
    assert response.status_code == 200
    token = response.json()["access_token"]
    sid = decode_access_token_claims(token)["sid"]
    assert sid != "old-session"
    assert client.get("/auth/me", headers=old_headers).status_code == 401
    assert client.post("/auth/activity", headers=old_headers).status_code == 401
    assert client.post("/auth/logout", headers=old_headers).status_code == 204
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).status_code == 200
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == sid
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("inactive", [False, True])
def test_recovery_never_revokes_session_for_invalid_credentials(setup, inactive):
    client, engine = setup
    if inactive:
        with Session(engine) as db:
            db.get(User, 1).is_active = False
            db.commit()
    assert sign_in(client, password="correct" if inactive else "wrong", replace=True).status_code == 401
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == "old-session"


def test_expired_session_can_sign_in_normally(setup):
    client, engine = setup
    with Session(engine) as db:
        db.get(User, 1).session_last_activity_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()
    assert sign_in(client).status_code == 200


def test_response_failure_does_not_leave_a_new_session(setup, monkeypatch):
    client, engine = setup
    def fail(*args):
        raise RuntimeError("Unable to build user response")
    monkeypatch.setattr(auth, "_user_summary", fail)
    with pytest.raises(RuntimeError, match="Unable to build"):
        sign_in(client, replace=True)
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == "old-session"


def assign_role(engine, name):
    with Session(engine) as db:
        user = db.get(User, 1)
        user.roles.append(Role(name=name))
        db.commit()


@pytest.mark.parametrize("role_name", ["SYSTEM_ADMINISTRATOR", "System Administrator", "system-administrator"])
def test_administrator_login_automatically_replaces_active_session(setup, role_name):
    client, engine = setup
    assign_role(engine, role_name)
    old_headers = {"Authorization": f"Bearer {create_access_token('tester', 'old-session')}"}
    response = sign_in(client)
    assert response.status_code == 200
    token = response.json()["access_token"]
    sid = decode_access_token_claims(token)["sid"]
    assert sid != "old-session"
    assert client.get("/auth/me", headers=old_headers).status_code == 401
    assert client.post("/auth/activity", headers=old_headers).status_code == 401
    assert client.post("/auth/logout", headers=old_headers).status_code == 204
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == sid
    # The next admin login takes over again, without requiring a UI confirmation.
    next_response = sign_in(client)
    assert next_response.status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {next_response.json()['access_token']}"}).status_code == 200


@pytest.mark.parametrize("inactive", [False, True])
def test_administrator_takeover_requires_valid_active_credentials(setup, inactive):
    client, engine = setup
    assign_role(engine, "SYSTEM_ADMINISTRATOR")
    if inactive:
        with Session(engine) as db:
            db.get(User, 1).is_active = False
            db.commit()
    assert sign_in(client, password="correct" if inactive else "wrong").status_code == 401
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == "old-session"


@pytest.mark.parametrize("role_name", ["ADMIN", "AP", "ACCOUNTANT"])
def test_other_roles_keep_existing_session_rule(setup, role_name):
    client, engine = setup
    assign_role(engine, role_name)
    assert sign_in(client).status_code == 409
    with Session(engine) as db:
        assert db.get(User, 1).active_session_id == "old-session"
