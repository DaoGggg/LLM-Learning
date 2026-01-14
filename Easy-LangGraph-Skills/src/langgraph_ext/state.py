from __future__ import annotations

import operator

from langgraph.graph import add_messages
from typing_extensions import TypedDict, Annotated




class SkillAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    selected_skill: str | None
    skill_docs_injected: bool
    skill_context: str | None
