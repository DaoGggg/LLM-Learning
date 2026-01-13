from __future__ import annotations

import re
from typing import Literal, Optional

from langchain.messages import SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END

from ..skills.registry import SkillRegistry
from ..skills.loader import SkillLoader
from ..skills.executor import SkillExecutor
from .state import SkillAgentState
from skills.skill_manager import SkillManager

# 严格匹配协议输出，避免“随便提到 skill 名”就误触发
_SKILL_SELECT_RE = re.compile(r"^I will use the (.+?) skill\s*$", re.IGNORECASE)


def create_skill_agent(
        model,
        skills_dir: str,
        enabled_skills: list[str],
        base_system_prompt: str = "You are a helpful assistant.",
):
    # 1) scan skills (metadata only)
    registry = SkillRegistry(skills_dir)
    registry.scan()

    runtimes = registry.subset(enabled_skills)
    loader = SkillLoader(runtimes)

    # 2) reuse your existing SkillManager for execution
    skill_manager = SkillManager(skill_dir=skills_dir)
    executor = SkillExecutor(skill_manager)

    # 3) Tools: one generic tool to execute commands
    @tool
    def run_command(command: str, working_dir: Optional[str] = None) -> str:
        """
        Execute a command (typically `python <script>.py ...`).
        The runtime will locate scripts inside enabled skills' scripts/ folders.
        """
        ok, stdout, stderr = executor.run_command(command, working_dir=working_dir)
        if ok:
            return stdout.strip() or "(ok)"
        return f"(failed)\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"

    tools_by_name = {run_command.name: run_command}
    model_with_tools = model.bind_tools([run_command])

    # 4) Nodes
    def llm_node(state: SkillAgentState):
        sys = base_system_prompt + "\n" + loader.build_skill_summaries()
        msg = model_with_tools.invoke([SystemMessage(content=sys)] + state["messages"])
        return {"messages": [msg]}

    def skill_docs_node(state: SkillAgentState):
        skill = state.get("selected_skill")
        if not skill:
            return {"skill_docs_injected": False}

        md = loader.load_full_skill_markdown(skill) or ""
        scripts = loader.build_scripts_inventory(skill)
        refs = loader.build_reference_inventory(skill)

        injected = (
            f"## Loaded Skill: {skill}\n\n"
            f"{md}\n\n"
            f"{scripts}\n"
            f"{refs}\n"
            "Now follow the skill instructions and output tool calls / commands as needed.\n"
        )
        return {
            "messages": [SystemMessage(content=injected)],
            "skill_docs_injected": True,
        }

    def tool_node(state: SkillAgentState):
        last = state["messages"][-1]
        outputs = []
        for tc in last.tool_calls:
            tool_fn = tools_by_name[tc["name"]]
            obs = tool_fn.invoke(tc["args"])
            outputs.append(ToolMessage(content=obs, tool_call_id=tc["id"]))
        return {"messages": outputs}

    # 5) Router
    def _extract_selected_skill(text: str) -> Optional[str]:
        m = _SKILL_SELECT_RE.match((text or "").strip())
        if not m:
            return None
        return m.group(1).strip()

    def route(state: SkillAgentState) -> Literal["tool_node", "skill_docs_node", END]:
        last = state["messages"][-1]

        # Tool call?
        if getattr(last, "tool_calls", None):
            if last.tool_calls:
                return "tool_node"

        # Skill selection?
        skill = _extract_selected_skill(getattr(last, "content", ""))
        if skill and (not state.get("skill_docs_injected", False)):
            # 只允许启用集合内的 skill
            if skill in runtimes:
                return "skill_docs_node"

        return END

    # 6) Build graph (loop)
    g = StateGraph(SkillAgentState)
    g.add_node("llm_node", llm_node)
    g.add_node("skill_docs_node", skill_docs_node)
    g.add_node("tool_node", tool_node)

    g.add_edge(START, "llm_node")
    g.add_conditional_edges("llm_node", route, ["tool_node", "skill_docs_node", END])
    g.add_edge("skill_docs_node", "llm_node")
    g.add_edge("tool_node", "llm_node")

    return g.compile()
