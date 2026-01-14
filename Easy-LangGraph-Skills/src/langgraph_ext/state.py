from __future__ import annotations

import operator

from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict, Annotated



class SkillAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    selected_skill: str | None
    skill_docs_injected: bool
