import asyncio

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services.session_manager import SessionManager
import src.api.routes as routes

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_redis_for_api_tests(monkeypatch):
    """Keep route tests isolated from an external Redis service."""
    redis_client = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(routes, "session_manager", SessionManager(redis_client))
    yield
    asyncio.run(redis_client.aclose())

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_session_dev_mode():
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json()["user_id"] == 99999999

def test_next_hand():
    before = client.get("/api/session").json()["btn_position"]
    response = client.post("/api/session/next-hand")
    assert response.status_code == 200
    assert response.json()["btn_position"] != before

def test_preflop_decision():
    response = client.post("/api/decision/preflop", json={"hero_combo": "AJs"})
    assert response.status_code == 200
    assert "action" in response.json()
    assert tuple(response.json()["action_ranges"]) == ("push", "raise", "isolate", "call")


def test_facing_action_decision_accepts_villain_position():
    response = client.post(
        "/api/decision/preflop",
        json={
            "hero_combo": "AJs",
            "facing_action": "OPEN_2.5X",
            "villain_position": "CO",
        },
    )

    assert response.status_code == 200
    assert response.json()["details"]["villain_position"] == "CO"


def test_preflop_request_validation():
    response = client.post("/api/decision/preflop", json={"hero_combo": "not-a-hand"})
    assert response.status_code == 422

    response = client.post("/api/decision/preflop", json={"facing_action": "limp"})
    assert response.status_code == 422


def test_postflop_request_validation():
    response = client.post(
        "/api/decision/postflop",
        json={"hero_cards": "AsKd", "flop_cards": "2h3c"},
    )
    assert response.status_code == 422
