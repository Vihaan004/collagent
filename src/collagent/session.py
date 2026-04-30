from langgraph.checkpoint.memory import MemorySaver

from collagent.graph import create_graph, stream_turn


class Session:
    def __init__(self) -> None:
        checkpointer = MemorySaver()
        self._graph = create_graph(checkpointer=checkpointer)
        self._config = {"configurable": {"thread_id": "session"}}

    def send(self, user_input: str) -> None:
        stream_turn(self._graph, user_input, self._config)
