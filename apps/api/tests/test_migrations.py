import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.core.db import Base
import app.models  # noqa: F401


def test_alembic_upgrade_matches_models_and_downgrades():
    api_dir = Path(__file__).parents[1]
    db_path = Path(tempfile.mkdtemp()) / "mig.sqlite3"
    url = f"sqlite:///{db_path}"
    env = {**os.environ, "DATABASE_URL": url}
    run = lambda *a: subprocess.run([sys.executable, "-m", "alembic", "-x", f"url={url}", *a], cwd=api_dir, env=env, capture_output=True, text=True)  # noqa: E731
    up = run("upgrade", "head")
    assert up.returncode == 0, up.stderr
    tables = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    assert run("downgrade", "base").returncode == 0
