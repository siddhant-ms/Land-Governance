"""Password hashing, JWT, and role/permission enforcement (API layer)."""
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import User

ROLES = ("public", "researcher", "analyst", "expert", "admin")
AUTHENTICATED_ROLES = ("researcher", "analyst", "expert", "admin")

# capability -> roles allowed. "public" means unauthenticated callers are allowed too.
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "corpus.read_public": ROLES,
    "map.read_public": ROLES,
    "workspace.write": AUTHENTICATED_ROLES,
    "scenario.run": AUTHENTICATED_ROLES,
    "brief.export": AUTHENTICATED_ROLES,
    "data.restricted": ("analyst", "expert", "admin"),
    "scenario.export": ("analyst", "expert", "admin"),
    "evidence.review": ("expert", "admin"),  # approve documents, annotate sources
    "model.review": ("expert", "admin"),
    "admin.manage": ("admin",),  # ingest, metadata, users, models, audit
}

# document access level -> capability required to see it
ACCESS_CAPABILITY = {"public": "corpus.read_public", "restricted": "data.restricted", "internal": "admin.manage"}


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt(rounds=10)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user.id), "role": user.role.name, "iat": now,
               "exp": now + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def role_has(role: str, capability: str) -> bool:
    return role in PERMISSIONS.get(capability, ())


def _user_from_request(request: Request, db: Session) -> User | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    s = get_settings()
    try:
        claims = jwt.decode(header[7:], s.jwt_secret, algorithms=[s.jwt_algorithm])
        uid = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "INVALID_TOKEN", "Your session is invalid or has expired. Please sign in again.")
    user = db.scalar(select(User).where(User.id == uid))
    # role is always re-read from the DB: a stale token can never keep elevated privileges
    if not user or user.status != "active":
        raise AppError(401, "INVALID_TOKEN", "Your session is invalid or has expired. Please sign in again.")
    return user


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user = _user_from_request(request, db)
    request.state.user = user
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise AppError(401, "AUTH_REQUIRED", "Sign in to use this feature.")
    return user


def role_of(user: User | None) -> str:
    return user.role.name if user else "public"


def require(capability: str):
    """Dependency factory enforcing a capability. Unauthenticated -> 401, wrong role -> 403."""
    def _dep(user: User | None = Depends(optional_user)) -> User | None:
        role = role_of(user)
        if role_has(role, capability):
            return user
        if user is None:
            raise AppError(401, "AUTH_REQUIRED", "Sign in to use this feature.")
        raise AppError(403, "FORBIDDEN", "Your role does not have permission for this action.",
                       {"capability": capability, "role": role})
    return _dep


def can_access(role: str, access_level: str) -> bool:
    return role_has(role, ACCESS_CAPABILITY.get(access_level, "admin.manage"))


def allowed_access_levels(role: str) -> list[str]:
    return [lvl for lvl in ACCESS_CAPABILITY if can_access(role, lvl)]
