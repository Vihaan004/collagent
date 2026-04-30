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
from collagent.canvas_tools import CANVAS_TOOLS

_tools = [calculator, *CANVAS_TOOLS]

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


model = ChatOpenAI(
    api_key=_env("OPENAI_API_KEY", "LLM_API_KEY"),
    base_url=_env("OPENAI_BASE_URL", default="https://openai.rc.asu.edu/v1"),
    model=_env("MODEL_NAME", default="qwen3-30b-a3b-instruct-2507"),
    temperature=float(_env("TEMPERATURE", default="0.0")),
    streaming=True,
)
model_with_tools = model.bind_tools(_tools)


# ==================== nodes ====================
def llm_node(state: AgentState) -> AgentState:
    response = model_with_tools.invoke(
        [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
    )
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def route_after_llm(state: AgentState) -> Literal["tool_node", "__end__"]:
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END


# ==================== graph ====================
def create_graph(checkpointer=None):
    graph = StateGraph(AgentState)
    graph.add_node("llm_node", llm_node)
    graph.add_node("tool_node", ToolNode(_tools))
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", route_after_llm, ["tool_node", END])
    graph.add_edge("tool_node", "llm_node")
    return graph.compile(checkpointer=checkpointer)


# ==================== streaming ====================
def stream_turn(graph, user_input: str, config: dict) -> None:
    in_model_text = False

    for chunk in graph.stream(
        {"messages": [HumanMessage(content=user_input)], "llm_calls": 0},
        config=config,
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] != "messages":
            continue

        message_chunk, _ = chunk["data"]
        tool_calls = getattr(message_chunk, "tool_calls", None) or []
        message_type = getattr(message_chunk, "type", None)

        if tool_calls:
            if in_model_text:
                print()
                in_model_text = False
            for call in tool_calls:
                name = call.get("name", "") if isinstance(call, dict) else ""
                args = call.get("args", {}) if isinstance(call, dict) else {}
                if name:  # skip partial chunks that only carry args
                    print(f"  [tool] {name} {args}")

        if message_type == "tool":
            if in_model_text:
                print()
                in_model_text = False
            name = getattr(message_chunk, "name", "tool")
            content = message_chunk.content or ""
            print(f"  [result] {name}: {content}")
            continue

        content = message_chunk.content
        if content and not content.isspace():  # skip whitespace-only chunks (e.g. trailing \n\n before a tool call)
            if not in_model_text:
                print("COLLAGENT: ", end="", flush=True)
            print(content, end="", flush=True)
            in_model_text = True

    if in_model_text:
        print()
