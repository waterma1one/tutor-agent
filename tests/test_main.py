"""The HTTP and websocket entry points, with the voice pipeline stubbed out."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main


@pytest.fixture
def client(monkeypatch):
    started = []

    async def fake_run_bot(websocket):
        started.append(websocket)
        await websocket.close()

    monkeypatch.setattr(main, "run_bot", fake_run_bot)
    client = TestClient(main.app)
    client.started = started
    return client


def test_websocket_from_the_frontend_starts_a_class(client):
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        with pytest.raises(WebSocketDisconnect):
            ws.receive_bytes()
    assert len(client.started) == 1


def test_websocket_from_another_site_is_refused(client):
    # Any page the student visits could otherwise open a class on their key.
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}):
            pass
    assert refused.value.code == 1008
    assert client.started == []


def test_websocket_without_an_origin_is_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass
    assert client.started == []


def test_allowed_origins_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://school.example, http://localhost:4000")
    assert main.allowed_origins() == {"https://school.example", "http://localhost:4000"}


def test_slides_lists_the_deck(client):
    slides = client.get("/slides").json()
    assert [s["number"] for s in slides] == list(range(1, 9))
