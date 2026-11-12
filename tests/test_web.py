import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app

PASSWORD = "password123"


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def signed_in(client):
    client.post("/register", data={"username": "tester", "password": PASSWORD, "confirm": PASSWORD})
    return client


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_pages_render_for_a_signed_in_user(signed_in):
    for url in ("/", "/prices", "/recipes"):
        assert signed_in.get(url).status_code == 200


def test_full_flow_wallet_plan_shopping(signed_in):
    signed_in.post("/wallet/topup", data={"amount": 400000})
    resp = signed_in.post("/plans", data={"period": "week", "budget": 300000, "start": "2026-11-02"}, follow_redirects=False)
    assert resp.status_code == 303
    plan_url = resp.headers["location"]
    assert "Trưa" in signed_in.get(plan_url).text
    shopping = signed_in.get(plan_url.replace("/plans/", "/shopping/"))
    assert "Tổng" in shopping.text


def test_plan_without_enough_money_shows_message(signed_in):
    resp = signed_in.post("/plans", data={"period": "week", "budget": 300000, "start": "2026-11-02"}, follow_redirects=True)
    assert "Số dư ví không đủ" in resp.text


def test_substitute_without_key_keeps_list_and_shows_notice(signed_in):
    signed_in.post("/wallet/topup", data={"amount": 400000})
    plan_url = signed_in.post("/plans", data={"period": "week", "budget": 300000, "start": "2026-11-02"}).url.path
    resp = signed_in.post(plan_url.replace("/plans/", "/shopping/") + "/substitute", data={"item_id": 1})
    assert resp.status_code == 200
    assert "tạm thời không khả dụng" in resp.text and "Tổng" in resp.text


def test_substitutes_filter_excluded_words(monkeypatch):
    class Reply:
        def raise_for_status(self): pass
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '["tôm khô", "đậu hũ", "trứng"]'}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: Reply())
    assert ai.suggest_substitutes("thịt", ["tôm"]) == ["đậu hũ", "trứng"]


def test_rate_limit_becomes_ai_error(monkeypatch):
    import httpx

    def limited(*a, **k):
        raise httpx.HTTPStatusError("429", request=None, response=None)

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai.httpx, "post", limited)
    try:
        ai.suggest_substitutes("thịt", [])
    except ai.AIError:
        return
    raise AssertionError("expected AIError")
