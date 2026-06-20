# src/collagent/memory_tools.py
"""Per-user memory tools: the chat agent curates durable facts about the student
through these CRUD tools (ChatGPT/Claude-style). Every tool is scoped to user_id."""
from langchain.tools import tool

from collagent import db


def make_memory_tools(user_id: str) -> list:
    @tool("remember")
    def remember(content: str, kind: str = "fact") -> str:
        """Save a durable fact about the student for future conversations — a stable
        preference, goal, constraint, or detail they shared (e.g. 'Prefers FPGA
        research', 'Graduating Spring 2027'). Do NOT store transient chit-chat or
        anything already in their profile. `kind` is a free label like 'fact',
        'goal', or 'preference'."""
        m = db.create_memory(user_id, content, kind)
        return f"Remembered (id {m.id}): {m.content}"

    @tool("list_memories")
    def list_memories() -> str:
        """List everything currently remembered about the student, each with its id.
        Use this to find an id before updating or forgetting a memory."""
        mems = db.get_memories(user_id)
        if not mems:
            return "No memories stored yet."
        return "\n".join(f"- [{m.id}] {m.content}" for m in mems)

    @tool("update_memory")
    def update_memory(memory_id: str, content: str) -> str:
        """Revise an existing memory's content. Get the id from list_memories first."""
        try:
            m = db.update_memory(user_id, memory_id, content)
        except ValueError:
            return f"No memory with id {memory_id}."
        return f"Updated (id {m.id}): {m.content}"

    @tool("forget")
    def forget(memory_id: str) -> str:
        """Delete a memory the student no longer wants kept, or that has become wrong.
        Get the id from list_memories first."""
        db.delete_memory(user_id, memory_id)
        return f"Forgot memory {memory_id}."

    return [remember, list_memories, update_memory, forget]
