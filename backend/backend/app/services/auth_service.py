from fastapi import HTTPException

from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
)

from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def login(
        self,
        username: str,
        password: str,
    ):

        user = self.repository.find_by_username(username)

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Username atau password salah",
            )

        if not verify_password(
            password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=401,
                detail="Username atau password salah",
            )

        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
        }

    def register(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
    ):

        if self.repository.find_by_username(username):
            raise HTTPException(
                status_code=409,
                detail="Username already exists",
            )

        if self.repository.find_by_email(email):
            raise HTTPException(
                status_code=409,
                detail="Email already exists",
            )

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_active=True,
        )

        return self.repository.create(user)