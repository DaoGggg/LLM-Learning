from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Optional


from langchain.tools import tool
from langchain_core.messages import ToolMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END

from langgraph_ext.registry import SkillRegistry
from langgraph_ext.loader import SkillLoader
from langgraph_ext.executor import SkillExecutor
from .state import SkillAgentState
from langgraph_ext.skill_manager import SkillManager

# 严格匹配协议输出，避免“随便提到 skill 名”就误触发
_SKILL_SELECT_RE = re.compile(r"^I will use the (.+?) skill\s*$", re.IGNORECASE)
PROJECT_ROOT=Path(__file__).parent.parent

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
    executor = SkillExecutor(skill_manager,default_working_dir=str(PROJECT_ROOT))

    # 3) Tools: one generic tool to execute commands
    @tool
    def run_command(command: str, working_dir: Optional[str] = None) -> str:
        """
        Execute a command (typically `python <script>.py ...`).
        The runtime will locate scripts inside enabled skills' scripts/ folders.
        """
        ok, stdout, stderr = executor.run_command(command, working_dir=working_dir)
        stdout = stdout or ""
        stderr = stderr or ""
        if ok:
            return stdout.strip() or "(ok)"
        return f"(failed)\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


    tools_by_name = {run_command.name: run_command}
    model_with_tools = model.bind_tools([run_command])

    # 4) Nodes
    def llm_node(state: SkillAgentState):
        sys = base_system_prompt + "\n" + loader.build_skill_summaries()
        if state.get("skill_context"):
            sys += "\n\n" + state["skill_context"]
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
            f"## Loaded Skill: {skill}\n\n{md}\n\n{scripts}\n{refs}\n"
            "IMPORTANT: Use ONLY script names from the Scripts list. Do NOT invent names.\n"
        )
        return {"skill_context": injected, "skill_docs_injected": True}

    def _tool_calls_of(msg) -> list[dict]:
        # 兼容不同版本：tool_calls 或 additional_kwargs["tool_calls"]
        tcs = getattr(msg, "tool_calls", None)
        if tcs:
            return tcs
        ak = getattr(msg, "additional_kwargs", {}) or {}
        return ak.get("tool_calls") or []

    def tool_node(state: SkillAgentState):
        last = state["messages"][-1]

        # ✅ 只允许 last 是 AIMessage
        if not isinstance(last, AIMessage):
            return {}

        tcs = _tool_calls_of(last)
        if not tcs:
            # ✅ 没有 tool_calls 就绝不产出 ToolMessage
            return {}

        outputs = []
        for tc in tcs:
            try:
                tool_fn = tools_by_name[tc["name"]]
                obs = tool_fn.invoke(tc["args"])
                outputs.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
            except Exception as e:
                outputs.append(ToolMessage(content=f"TOOL_ERROR: {e}", tool_call_id=tc["id"]))

        return {"messages": outputs}

    # 5) Router
    def _extract_selected_skill(text: str) -> Optional[str]:
        m = _SKILL_SELECT_RE.match((text or "").strip())
        if not m:
            return None
        return m.group(1).strip()

    def route(state: SkillAgentState) -> Literal["tool_node", "skill_docs_node", END]:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and _tool_calls_of(last):
            return "tool_node"
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

    def select_skill_node(state: SkillAgentState):
        last = state["messages"][-1]
        skill = _extract_selected_skill(getattr(last, "content", ""))
        if skill and (skill in runtimes):
            return {"selected_skill": skill}
        return {}

    # 6) Build graph (loop)
    g = StateGraph(SkillAgentState)
    g.add_node("llm_node", llm_node)
    g.add_node("select_skill_node", select_skill_node)
    g.add_edge("llm_node", "select_skill_node")
    g.add_conditional_edges("select_skill_node", route, ["tool_node","skill_docs_node",END])

    g.add_node("skill_docs_node", skill_docs_node)
    g.add_node("tool_node", tool_node)

    g.add_edge(START, "llm_node")
    g.add_edge("skill_docs_node", "llm_node")
    g.add_edge("tool_node", "llm_node")

    return g.compile()
