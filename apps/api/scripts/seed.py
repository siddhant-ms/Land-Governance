"""python -m scripts.seed  (run from apps/api). Creates tables if needed (dev/SQLite) and seeds demo data."""
import json

from app.core.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.seed.run import seed_all

if __name__ == "__main__":
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)  # on PostgreSQL use `alembic upgrade head`
    with SessionLocal() as db:
        print(json.dumps(seed_all(db), indent=2, default=str))
