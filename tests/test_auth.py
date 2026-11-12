from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import services as sv
from app.main import app
from app.models import Plan, User, Wallet
from app.security import hash_password, verify_password

PASSWORD = "correct-horse-battery"


def sign_up(client, username="alice", password=PASSWORD):
    return client.post("/register", data={"username": username, "password": password, "confirm": password})


# ---------- passwords ----------

def test_password_is_stored_as_a_salted_hash():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored
    assert stored.startswith("scrypt$")
    assert hash_password(PASSWORD) != stored  # a new salt every time
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong-password", stored)


def test_malformed_stored_hash_never_verifies():
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "scrypt$a$b$c$d$e")


# ---------- accounts ----------

def test_register_rejects_bad_input(db):
    with pytest.raises(ValueError):
        sv.register_user(db, "ab", PASSWORD, PASSWORD)  # username too short
    with pytest.raises(ValueError):
        sv.register_user(db, "bad name!", PASSWORD, PASSWORD)  # space and symbol
    with pytest.raises(ValueError):
        sv.register_user(db, "alice", "short", "short")  # password too short
    with pytest.raises(ValueError):
        sv.register_user(db, "alice", PASSWORD, "different-one")  # confirmation does not match


def test_usernames_are_unique_ignoring_case(db):
    sv.register_user(db, "Alice", PASSWORD, PASSWORD)
    with pytest.raises(ValueError):
        sv.register_user(db, "alice", PASSWORD, PASSWORD)


def test_login_needs_the_right_password(db):
    sv.register_user(db, "alice", PASSWORD, PASSWORD)
    assert sv.authenticate_user(db, "ALICE", PASSWORD).username == "alice"
    with pytest.raises(ValueError):
        sv.authenticate_user(db, "alice", "wrong-password")
    with pytest.raises(ValueError):
        sv.authenticate_user(db, "nobody", PASSWORD)


# ---------- web: who can see what ----------

def test_pages_redirect_to_login_when_signed_out(db):
    client = TestClient(app)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login")
    for url in ("/prices", "/recipes"):
        assert client.get(url, follow_redirects=False).status_code == 303
    resp = client.post("/wallet/topup", data={"amount": 100}, follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"].startswith("/login")


def test_sign_up_signs_in_and_logout_signs_out(db):
    client = TestClient(app)
    resp = sign_up(client)
    assert resp.url.path == "/"
    assert "Xin chào" in client.get("/").text
    client.post("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_wrong_password_shows_a_message(db):
    client = TestClient(app)
    sign_up(client)
    client.post("/logout")
    resp = client.post("/login", data={"username": "alice", "password": "not-the-password"}, follow_redirects=True)
    assert "Sai tên đăng nhập hoặc mật khẩu" in resp.text


def test_each_user_has_their_own_wallet_and_plans(db):
    alice, bob = TestClient(app), TestClient(app)
    sign_up(alice, "alice")
    sign_up(bob, "bob")
    alice.post("/wallet/topup", data={"amount": 400_000})
    plan_path = alice.post("/plans", data={"period": "week", "budget": 300_000, "start": "2026-11-02"}).url.path

    balances = {w.user_id: w.balance for w in db.scalars(select(Wallet))}
    alice_id = db.scalar(select(User.id).where(User.username == "alice"))
    bob_id = db.scalar(select(User.id).where(User.username == "bob"))
    assert balances[alice_id] == 100_000
    assert balances.get(bob_id, 0) == 0

    assert bob.get(plan_path).status_code == 404
    assert bob.get(plan_path.replace("/plans/", "/shopping/")).status_code == 404
    assert bob.post(plan_path + "/cheaper", follow_redirects=False).status_code == 404
    assert plan_path not in bob.get("/").text


def test_plans_from_before_accounts_are_hidden(db):
    legacy = Plan(period="week", start_date=date(2026, 11, 2), budget=100_000, exclusions="")  # no user_id
    db.add(legacy)
    db.commit()
    client = TestClient(app)
    sign_up(client)
    assert client.get(f"/plans/{legacy.id}").status_code == 404
    assert f"/plans/{legacy.id}" not in client.get("/").text


def test_stored_user_is_checked_on_each_request(db):
    client = TestClient(app)
    sign_up(client)
    db.delete(db.scalar(select(User).where(User.username == "alice")))
    db.commit()
    assert client.get("/", follow_redirects=False).status_code == 303
