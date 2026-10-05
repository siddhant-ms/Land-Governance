"""Roles, organizations and demo accounts. Passwords are DEMO credentials for local/judging use only."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Organization, Role, User

ROLE_DESCRIPTIONS = {
    "public": "Unauthenticated visitor: public corpus and public maps",
    "researcher": "Saves workspaces, briefs and scenarios",
    "analyst": "Official/analyst: protected datasets, scenario export",
    "expert": "Reviews evidence, annotates sources, reviews model assumptions",
    "admin": "Ingests documents, manages users, models and audit logs",
}
DEMO_PASSWORD = "Demo@12345"
DEMO_USERS = [
    ("Asha Researcher", "researcher@demo.sih", "researcher", "Demo Academic Consortium (fictional)", "academic"),
    ("Arjun Analyst", "analyst@demo.sih", "analyst", "Demo State Revenue Studies Unit (fictional)", "government"),
    ("Meera Expert", "expert@demo.sih", "expert", "Demo Legal Studies Centre (fictional)", "academic"),
    ("Admin User", "admin@demo.sih", "admin", "SIH26019 Prototype Team", "other"),
]


def seed_identity(db: Session) -> None:
    roles = {}
    for name, desc in ROLE_DESCRIPTIONS.items():
        r = db.scalar(select(Role).where(Role.name == name)) or Role(name=name, description=desc)
        db.add(r)
        roles[name] = r
    db.flush()
    pw = hash_password(DEMO_PASSWORD)
    for name, email, role, org_name, org_type in DEMO_USERS:
        org = db.scalar(select(Organization).where(Organization.name == org_name))
        if not org:
            org = Organization(name=org_name, type=org_type, verified_status="demo")
            db.add(org)
            db.flush()
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(name=name, email=email, password_hash=pw, role_id=roles[role].id, org_id=org.id))
    db.commit()
