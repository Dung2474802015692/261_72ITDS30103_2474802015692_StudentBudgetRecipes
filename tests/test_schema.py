from sqlalchemy import create_engine, inspect, text

from app.db import Base, upgrade_schema


def test_upgrade_adds_account_columns_and_keeps_old_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # the tables as they were before accounts existed
        conn.execute(text("CREATE TABLE wallet (id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)"))
        conn.execute(text(
            "CREATE TABLE plan (id INTEGER PRIMARY KEY, period VARCHAR NOT NULL, "
            "start_date DATE NOT NULL, budget INTEGER NOT NULL, exclusions VARCHAR DEFAULT '')"
        ))
        conn.execute(text("INSERT INTO wallet (id, balance) VALUES (1, 500000)"))

    Base.metadata.create_all(engine)  # adds the new app_user table, leaves the old ones alone
    upgrade_schema(engine)
    upgrade_schema(engine)  # a second run changes nothing

    insp = inspect(engine)
    assert "user_id" in {c["name"] for c in insp.get_columns("wallet")}
    assert "user_id" in {c["name"] for c in insp.get_columns("plan")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT balance FROM wallet WHERE id = 1")).scalar() == 500_000
