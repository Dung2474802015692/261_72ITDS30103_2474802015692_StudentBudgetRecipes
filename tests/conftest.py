import os
import tempfile

# Must be set before the app is imported so tests never touch the real budget.db.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ.pop("GEMINI_API_KEY", None)
os.environ["SESSION_SECRET"] = "test-only-secret-never-used-outside-tests"

import pytest

from app import services as sv
from app.db import Base, SessionLocal, engine
from app.seed import seed


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
        yield session


@pytest.fixture
def user(db):
    return sv.register_user(db, "tester", "password123", "password123")
