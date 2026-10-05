from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.core.security import create_token, current_user, hash_password, verify_password
from app.models import Role, User
from app.schemas.common import LoginIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("not-a-real-password")  # constant-time-ish response for unknown emails


def user_out(u: User) -> dict:
    return {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role.name,
            "organization": u.organization.name if u.organization else None}


@router.post("/login", dependencies=[Depends(rate_limit("auth", 10, 60))])
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, u.password_hash if u else _DUMMY_HASH)
    if not u or not ok or u.status != "active":
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")
    audit.record(db, request, u, "USER_LOGIN", "user", u.id)
    return {"access_token": create_token(u), "token_type": "bearer", "user": user_out(u)}


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("auth", 10, 60))])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise AppError(409, "EMAIL_EXISTS", "An account with this email already exists.")
    role = db.scalar(select(Role).where(Role.name == "researcher"))  # self-service always yields the lowest authenticated role
    u = User(name=body.name.strip(), email=body.email.lower(), password_hash=hash_password(body.password), role_id=role.id)
    db.add(u)
    db.commit()
    db.refresh(u)
    audit.record(db, request, u, "USER_REGISTERED", "user", u.id)
    return {"access_token": create_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
