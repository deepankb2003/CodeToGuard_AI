"""
Points the DB at a throwaway SQLite file before any app module (which reads
settings.database_url at import time) gets imported by a test module.
"""
import os
import tempfile
from pathlib import Path

import pytest

_db_path = Path(tempfile.gettempdir()) / "codeguardian_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_path}")


@pytest.fixture(autouse=True, scope="session")
def _clean_test_db():
    if _db_path.exists():
        _db_path.unlink()
    yield
    from app.db.session import engine
    engine.dispose()
    try:
        _db_path.unlink(missing_ok=True)
    except PermissionError:
        pass
