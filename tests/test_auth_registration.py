from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import router
from app.core.database import get_db
from app.core.security import verify_password
from app.models import Base
from app.models.user import User


def registration_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), session_factory


def test_register_creates_active_user_without_roles():
    client, session_factory = registration_client()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": " new.user ",
            "full_name": " New User ",
            "email": " NEW.USER@example.com ",
            "password": "secret",
        },
    )

    assert response.status_code == 201
    assert response.json()["requires_admin_access"] is True
    with session_factory() as db:
        user = db.query(User).filter(User.username == "new.user").one()
        assert user.email == "new.user@example.com"
        assert user.is_active is True
        assert user.roles == []
        assert verify_password("secret", user.password_hash)


def test_register_rejects_duplicate_username_and_email():
    client, _ = registration_client()
    payload = {
        "username": "new.user",
        "full_name": "New User",
        "email": "new.user@example.com",
        "password": "secret",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    duplicate_username = {**payload, "email": "other@example.com"}
    response = client.post("/api/v1/auth/register", json=duplicate_username)
    assert response.status_code == 409
    assert response.json()["detail"] == "Username is already registered"

    duplicate_email = {**payload, "username": "other.user"}
    response = client.post("/api/v1/auth/register", json=duplicate_email)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already registered"
