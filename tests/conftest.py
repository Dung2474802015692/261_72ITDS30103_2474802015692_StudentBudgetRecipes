import os
import tempfile

# Must be set before the app is imported so tests never touch the real budget.db.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ.pop("GEMINI_API_KEY", None)

import pytest

from app.db import Base, SessionLocal, engine
from app.seed import seed


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session)
        yield session
