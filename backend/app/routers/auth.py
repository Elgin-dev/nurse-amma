import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    BootstrapAdminRequest,
    CreateClinicianRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


@router.post("/bootstrap", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_first_admin(
    payload: BootstrapAdminRequest,
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> User:
    expected = settings.bootstrap_admin_token
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set JWT_SECRET_KEY in the server environment.",
        )
    if not expected or len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BOOTSTRAP_ADMIN_TOKEN must be configured with at least 32 characters",
        )
    if not bootstrap_token or not hmac.compare_digest(bootstrap_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bootstrap token")

    existing_user_id = db.scalar(select(User.id).limit(1))
    if existing_user_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap is only available before the first account exists")

    admin = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
    )
    try:
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to create the initial administrator") from exc
    except Exception:
        db.rollback()
        raise


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_clinician(
    payload: CreateClinicianRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> User:
    clinician = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="clinician",
        is_active=True,
    )
    try:
        db.add(clinician)
        db.commit()
        db.refresh(clinician)
        return clinician
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists") from exc
    except Exception:
        db.rollback()
        raise
