from __future__ import annotations

import operator
from typing import List

from langchain.messages import AnyMessage
from typing_extensions import Annotated, TypedDict


class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    llm_calls: int
