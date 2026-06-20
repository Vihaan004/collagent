# tests/test_memory_tools.py
from collagent import memory_tools
from collagent.models import Memory

MEM = Memory(id="m1", user_id="u1", content="Prefers FPGA research", kind="fact")


def _tools():
    return {t.name: t for t in memory_tools.make_memory_tools("u1")}


def test_remember_creates_and_confirms(monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_tools.db, "create_memory",
                        lambda uid, content, kind="fact": captured.update(uid=uid, content=content, kind=kind) or MEM)
    out = _tools()["remember"].invoke({"content": "Prefers FPGA research"})
    assert captured == {"uid": "u1", "content": "Prefers FPGA research", "kind": "fact"}
    assert "Prefers FPGA research" in out


def test_list_memories_renders_ids(monkeypatch):
    monkeypatch.setattr(memory_tools.db, "get_memories", lambda uid: [MEM])
    out = _tools()["list_memories"].invoke({})
    assert "m1" in out and "Prefers FPGA research" in out


def test_list_memories_empty(monkeypatch):
    monkeypatch.setattr(memory_tools.db, "get_memories", lambda uid: [])
    out = _tools()["list_memories"].invoke({})
    assert "no memories" in out.lower()


def test_update_memory_handles_missing(monkeypatch):
    def boom(uid, mid, content):
        raise ValueError("not found")
    monkeypatch.setattr(memory_tools.db, "update_memory", boom)
    out = _tools()["update_memory"].invoke({"memory_id": "nope", "content": "x"})
    assert "no memory" in out.lower()


def test_forget_deletes(monkeypatch):
    captured = {}
    monkeypatch.setattr(memory_tools.db, "delete_memory",
                        lambda uid, mid: captured.update(uid=uid, mid=mid))
    out = _tools()["forget"].invoke({"memory_id": "m1"})
    assert captured == {"uid": "u1", "mid": "m1"}
    assert "m1" in out
