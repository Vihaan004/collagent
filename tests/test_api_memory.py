# tests/test_api_memory.py
from collagent.api.routes import memory as memory_routes
from collagent.models import Memory

MEM = Memory(id="m1", user_id="00000000-0000-0000-0000-000000000001",
             content="Prefers FPGA research", kind="fact")


def test_list_memory(client, monkeypatch):
    monkeypatch.setattr(memory_routes.db, "get_memories", lambda uid: [MEM])
    res = client.get("/api/memory")
    assert res.status_code == 200
    assert res.json()[0]["content"] == "Prefers FPGA research"


def test_delete_memory(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_routes.db, "delete_memory",
                        lambda uid, mid: captured.update(uid=uid, mid=mid))
    res = client.delete("/api/memory/m1")
    assert res.status_code == 204
    assert captured["mid"] == "m1"
    assert captured["uid"] == "00000000-0000-0000-0000-000000000001"  # scoped to caller


def test_memory_unauthenticated_401():
    from fastapi.testclient import TestClient

    from collagent.api.main import app

    assert TestClient(app).get("/api/memory").status_code == 401
