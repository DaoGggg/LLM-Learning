from __future__ import annotations

import operator
from typing_extensions import TypedDict, Annotated
from langchain.messages import AnyMessage


class SkillAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    selected_skill: str | None
    skill_docs_injected: bool
