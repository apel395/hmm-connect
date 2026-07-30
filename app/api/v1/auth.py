from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import TokenResponse, UserSummary


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not user.is_active or not verify_password(
        form.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return TokenResponse(access_token=create_access_token(user.username))


@router.get("/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)):
    return user
