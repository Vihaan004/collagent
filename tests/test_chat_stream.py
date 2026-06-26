import json
import types

from collagent import graph as graph_mod
from collagent.api.routes.chat import sse_format
from collagent.graph import stream_events


def test_sse_format():
    line = sse_format({"type": "token", "content": "hi"})
    assert line == 'data: {"type": "token", "content": "hi"}\n\n'
    assert json.loads(line[len("data: "):].strip()) == {"type": "token", "content": "hi"}


class _FakeGraph:
    """Records the config stream_events hands to LangGraph."""

    def __init__(self):
        self.config = None

    def stream(self, _input, config, **_kw):
        self.config = config
        return iter([])


def test_stream_events_raises_recursion_limit_above_default():
    # The full dashboard pipeline needs more than LangGraph's default of 25 steps.
    g = _FakeGraph()
    list(stream_events(g, "hi", {"configurable": {"thread_id": "t"}}))
    assert g.config["recursion_limit"] == graph_mod._RECURSION_LIMIT
    assert g.config["recursion_limit"] > 25
    assert g.config["configurable"]["thread_id"] == "t"  # caller config preserved


def test_stream_events_lets_caller_override_recursion_limit():
    g = _FakeGraph()
    list(stream_events(g, "hi", {"configurable": {"thread_id": "t"}, "recursion_limit": 5}))
    assert g.config["recursion_limit"] == 5


def _msg_chunk(*, type="AIMessageChunk", content="", tool_calls=None, name=None):
    return types.SimpleNamespace(type=type, content=content, tool_calls=tool_calls or [], name=name)


def _messages_chunk(msg, node):
    # Mirror LangGraph v2 stream_mode="messages": {"type": "messages", "data": (msg, metadata)}.
    return {"type": "messages", "ns": (), "data": (msg, {"langgraph_node": node})}


class _ScriptedGraph:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, _input, config, **_kw):
        return iter(self._chunks)


def test_stream_events_emits_llm_node_tokens():
    g = _ScriptedGraph([_messages_chunk(_msg_chunk(content="Hello"), "llm_node")])
    out = list(stream_events(g, "hi", {"configurable": {}}))
    assert out == [{"type": "token", "content": "Hello"}]


def test_stream_events_drops_nested_tool_node_llm_tokens():
    # refresh_people/refresh_events rank candidates with a nested structured-output LLM
    # that runs under the tool node; its raw JSON must NOT leak into the chat, while the
    # legitimate tool result (a ToolMessage) is still surfaced.
    g = _ScriptedGraph([
        _messages_chunk(_msg_chunk(content='{"picks": [{"person_id": "abc"}]}'), "tool_node"),
        _messages_chunk(
            _msg_chunk(type="tool", content="People refreshed: 5 recommendations.", name="refresh_people"),
            "tool_node",
        ),
        _messages_chunk(_msg_chunk(content="Here are some people to reach out to:"), "llm_node"),
    ])
    out = list(stream_events(g, "hi", {"configurable": {}}))
    tokens = [e["content"] for e in out if e["type"] == "token"]
    assert tokens == ["Here are some people to reach out to:"]  # nested JSON dropped
    assert {"type": "tool_result", "name": "refresh_people",
            "content": "People refreshed: 5 recommendations."} in out


def test_stream_events_drops_nested_tool_node_tool_calls():
    # with_structured_output uses a function call under the hood; that phantom tool_call
    # from the nested ranking model must not surface as a 'tool' event.
    g = _ScriptedGraph([
        _messages_chunk(_msg_chunk(tool_calls=[{"name": "PersonRanking", "args": {}}]), "tool_node"),
        _messages_chunk(_msg_chunk(tool_calls=[{"name": "refresh_people", "args": {}}]), "llm_node"),
    ])
    out = list(stream_events(g, "hi", {"configurable": {}}))
    assert [e["name"] for e in out if e["type"] == "tool"] == ["refresh_people"]
