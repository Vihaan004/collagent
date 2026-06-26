from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from collagent.state import AgentState
from collagent.tools import calculator

# Canvas tools are temporarily disabled: the live Canvas API isn't wired up for the
# demo, so the agent should not reach for it (it errors when it tries). To re-enable,
# import CANVAS_TOOLS from collagent.canvas_tools and add `*CANVAS_TOOLS` below.
_tools = [calculator]

# How many graph steps a single turn may take. A full dashboard refresh chains ~9 tools
# (refresh_* → reads → save_dashboard_brief); at 2 steps per tool call that approaches
# LangGraph's default of 25 and trips GraphRecursionError mid-pipeline, so the first
# refresh on a cold thread fails and only the (checkpoint-resumed) second click finishes.
_RECURSION_LIMIT = 50

_SYSTEM_PROMPT = "You are a helpful Canvas LMS assistant. Be concise and accurate."

# ==================== environment + model ====================
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, *aliases: str, default: str | None = None) -> str | None:
    for key in (name, *aliases):
        value = os.getenv(key)
        if value:
            return value
    return default


def get_model() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=_env("OPENAI_API_KEY", "LLM_API_KEY"),
        base_url=_env("OPENAI_BASE_URL", default="https://openai.rc.asu.edu/v1"),
        model=_env("MODEL_NAME", default="qwen3-30b-a3b-instruct-2507"),
        temperature=float(_env("TEMPERATURE", default="0.0")),
        streaming=True,
    )


model = get_model()


# ==================== graph ====================
def create_graph(checkpointer=None, system_prompt: str = _SYSTEM_PROMPT, extra_tools: tuple = ()):
    tools = [*_tools, *extra_tools]
    bound = get_model().bind_tools(tools)

    def llm_node(state: AgentState) -> AgentState:
        response = bound.invoke([SystemMessage(content=system_prompt)] + state["messages"])
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    def route_after_llm(state: AgentState) -> Literal["tool_node", "__end__"]:
        if state["messages"][-1].tool_calls:
            return "tool_node"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", route_after_llm, ["tool_node", END])
    graph.add_edge("tool_node", "llm_node")
    return graph.compile(checkpointer=checkpointer)


# ==================== streaming ====================
def stream_events(graph, user_input: str, config: dict):
    """Yield {'type': 'token'|'tool'|'tool_result', ...} events for one turn."""
    config = {"recursion_limit": _RECURSION_LIMIT, **config}  # caller may override
    for chunk in graph.stream(
        {"messages": [HumanMessage(content=user_input)], "llm_calls": 0},
        config=config,
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] != "messages":
            continue

        message_chunk, metadata = chunk["data"]
        message_type = getattr(message_chunk, "type", None)

        # Tool results (ToolMessages) come from the tool node; surface them.
        if message_type == "tool":
            yield {
                "type": "tool_result",
                "name": getattr(message_chunk, "name", "tool"),
                "content": message_chunk.content or "",
            }
            continue

        # The agent's own text and tool decisions are produced only by the main
        # `llm_node`. Tools may make their own nested LLM calls (e.g. refresh_people /
        # refresh_events rank candidates with a structured-output model); those run
        # under the tool node and would otherwise leak their raw JSON into the chat.
        # Skip anything not produced by llm_node.
        if (metadata or {}).get("langgraph_node") != "llm_node":
            continue

        for call in getattr(message_chunk, "tool_calls", None) or []:
            name = call.get("name", "") if isinstance(call, dict) else ""
            args = call.get("args", {}) if isinstance(call, dict) else {}
            if name:  # skip partial chunks that only carry args
                yield {"type": "tool", "name": name, "args": args}

        content = message_chunk.content
        if content and not content.isspace():  # skip whitespace-only chunks (e.g. trailing \n\n before a tool call)
            yield {"type": "token", "content": content}


def stream_turn(graph, user_input: str, config: dict) -> None:
    """CLI printer over stream_events (keeps `collagent run` behavior)."""
    in_model_text = False
    for event in stream_events(graph, user_input, config):
        if event["type"] == "tool":
            if in_model_text:
                print()
                in_model_text = False
            print(f"  [tool] {event['name']} {event['args']}")
        elif event["type"] == "tool_result":
            if in_model_text:
                print()
                in_model_text = False
            print(f"  [result] {event['name']}: {event['content']}")
        else:
            if not in_model_text:
                print("COLLAGENT: ", end="", flush=True)
            print(event["content"], end="", flush=True)
            in_model_text = True
    if in_model_text:
        print()
