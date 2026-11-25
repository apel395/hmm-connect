from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth as auth_api
from app.api.v1 import exports as exports_api
from app.core import database as database_module
from app.core.config import settings
from app.core.db_scope import DATABASE_CLAIM, DATABASE_PARAM, DEMO_DB_KEY, PRIMARY_DB_KEY
from app.core.security import create_access_token, decode_access_token_claims
from app.models import Base
from app.models.export_job import ExportJob
from app.models.user import User


@pytest.fixture
def demo_environment(monkeypatch):
    engines = {
        PRIMARY_DB_KEY: create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        ),
        DEMO_DB_KEY: create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        ),
    }
    for engine in engines.values():
        Base.metadata.create_all(engine)

    with Session(engines[PRIMARY_DB_KEY]) as db:
        db.add(
            User(
                username="primary",
                email="primary@example.com",
                full_name="Primary User",
                password_hash="test-hash",
                is_active=True,
            )
        )
        db.commit()
    with Session(engines[DEMO_DB_KEY]) as db:
        db.add(
            User(
                username="demo",
                email="demo@hmm.demo",
                full_name="Demo User",
                password_hash="test-hash",
                is_active=True,
            )
        )
        db.commit()

    monkeypatch.setattr(settings, "DEMO_USERNAMES", "demo")
    monkeypatch.setattr(database_module, "Engines", engines)
    monkeypatch.setattr(
        database_module,
        "SessionFactories",
        {
            key: database_module.sessionmaker(autocommit=False, autoflush=False, bind=engine)
            for key, engine in engines.items()
        },
    )
    monkeypatch.setattr(
        auth_api,
        "verify_password",
        lambda plain, hashed: plain == "correct" and hashed == "test-hash",
    )

    app = FastAPI()
    app.include_router(auth_api.router)
    app.include_router(exports_api.router)
    with TestClient(app) as client:
        yield client, engines

    for engine in engines.values():
        engine.dispose()


def _login(client, username):
    return client.post(
        "/auth/login",
        data={"username": username, "password": "correct"},
    )


def _claims(response):
    return decode_access_token_claims(response.json()["access_token"])


def test_demo_login_authenticates_against_demo_db_and_signs_claim(demo_environment):
    client, engines = demo_environment
    response = _login(client, "demo")
    assert response.status_code == 200

    claims = _claims(response)
    assert claims[DATABASE_CLAIM] == DEMO_DB_KEY
    assert claims["sid"]

    with Session(engines[DEMO_DB_KEY]) as db:
        assert db.query(User).filter(User.username == "demo").one().active_session_id == claims["sid"]
    with Session(engines[PRIMARY_DB_KEY]) as db:
        assert db.query(User).filter(User.username == "primary").one().active_session_id is None

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "demo"


def test_primary_login_has_no_demo_claim(demo_environment):
    client, _ = demo_environment
    response = _login(client, "primary")
    assert response.status_code == 200
    assert DATABASE_CLAIM not in _claims(response)


def test_demo_session_heartbeat_and_logout_only_touch_demo_db(demo_environment):
    client, engines = demo_environment
    response = _login(client, "demo")
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/auth/activity", headers=headers).status_code == 204
    assert client.post("/auth/logout", headers=headers).status_code == 204

    with Session(engines[DEMO_DB_KEY]) as db:
        assert db.query(User).filter(User.username == "demo").one().active_session_id is None
    with Session(engines[PRIMARY_DB_KEY]) as db:
        assert db.query(User).filter(User.username == "primary").one().active_session_id is None


def test_unknown_database_claim_is_rejected(demo_environment):
    client, _ = demo_environment
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {
            "sub": "demo",
            "sid": "manual-session",
            DATABASE_CLAIM: "unknown",
            "exp": expires,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_demo_login_fails_closed_without_demo_database(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_USERNAMES", "demo")
    primary_factory = database_module.SessionFactories[PRIMARY_DB_KEY]
    monkeypatch.setattr(
        database_module, "SessionFactories", {PRIMARY_DB_KEY: primary_factory}
    )

    app = FastAPI()
    app.include_router(auth_api.router)
    with TestClient(app) as client:
        response = client.post(
            "/auth/login", data={"username": "demo", "password": "correct"}
        )
    assert response.status_code == 503


def test_export_job_carries_signed_database_scope(demo_environment):
    client, engines = demo_environment
    token = _login(client, "demo").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/exports",
        json={"export_type": "products", "params": {"catalog_type": "HOTEL"}},
        headers=headers,
    )
    assert response.status_code == 202
    assert DATABASE_PARAM not in response.json()["params"]

    with Session(engines[DEMO_DB_KEY]) as db:
        job = db.get(ExportJob, response.json()["job_id"])
        assert job.params[DATABASE_PARAM] == DEMO_DB_KEY
    with Session(engines[PRIMARY_DB_KEY]) as db:
        assert db.query(ExportJob).count() == 0

    from app.scripts.export_worker import _find_job_database

    assert _find_job_database(response.json()["job_id"]) == DEMO_DB_KEY


def test_database_key_for_session_resolves_registered_engines(demo_environment):
    _, engines = demo_environment

    with Session(engines[DEMO_DB_KEY]) as db:
        assert database_module.database_key_for_session(db) == DEMO_DB_KEY
    with Session(engines[PRIMARY_DB_KEY]) as db:
        assert database_module.database_key_for_session(db) == PRIMARY_DB_KEY


def _approval_actors():
    step = SimpleNamespace(
        status="PENDING",
        approved_by_id=None,
        decided_at=None,
        decision_comment=None,
    )
    request = SimpleNamespace(status="PENDING", current_step_order=1)
    user = SimpleNamespace(id=99)
    return step, request, user


def test_demo_scope_allows_single_login_to_complete_receiving_approval(monkeypatch):
    from app.services import approval as approval_service

    step, request, user = _approval_actors()
    monkeypatch.setattr(approval_service, "_lock_request", lambda db, request: request)
    monkeypatch.setattr(approval_service, "_select_current_step", lambda request, user: step)
    monkeypatch.setattr(approval_service, "has_receiving_approval", lambda request, user: True)
    monkeypatch.setattr(approval_service, "_advance_stage", lambda db, request: None)
    monkeypatch.setattr(approval_service, "database_key_for_session", lambda db: DEMO_DB_KEY)

    db = SimpleNamespace(flush=lambda: None)
    approval_service.approve_current_step(db, request=request, user=user, comment="demo")

    assert step.status == "APPROVED"
    assert step.approved_by_id == user.id


def test_primary_scope_still_requires_two_receiving_approvers(monkeypatch):
    from app.services import approval as approval_service

    step, request, user = _approval_actors()
    monkeypatch.setattr(approval_service, "_lock_request", lambda db, request: request)
    monkeypatch.setattr(approval_service, "_select_current_step", lambda request, user: step)
    monkeypatch.setattr(approval_service, "has_receiving_approval", lambda request, user: True)
    monkeypatch.setattr(approval_service, "_advance_stage", lambda db, request: None)
    monkeypatch.setattr(approval_service, "database_key_for_session", lambda db: PRIMARY_DB_KEY)

    with pytest.raises(HTTPException) as exc:
        approval_service.approve_current_step(object(), request=request, user=user)

    assert exc.value.status_code == 409
    assert step.status == "PENDING"
