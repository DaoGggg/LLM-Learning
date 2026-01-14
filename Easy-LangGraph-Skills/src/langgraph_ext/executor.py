from __future__ import annotations

from typing import Optional, Tuple
from pathlib import Path

from langgraph_ext.skill_manager import SkillManager


class SkillExecutor:
    """
    运行命令的薄封装，但负责把 working_dir 变成可控、存在的绝对路径。
    目标：避免模型/上层传入无效 cwd 导致 WinError 267，从而打断 tool_calls 链路。
    """

    def __init__(self, skill_manager: SkillManager, default_working_dir: Optional[str] = None):
        self.skill_manager = skill_manager

        if default_working_dir:
            self.default_working_dir = Path(default_working_dir).resolve()
        else:
            # 默认用当前进程工作目录（你在 test 里运行就会是 src/test）
            self.default_working_dir = Path.cwd().resolve()

    def _normalize_cwd(self, working_dir: Optional[str]) -> Path:
        # 1) 优先用传入 cwd，否则用默认
        cwd = Path(working_dir).expanduser() if working_dir else self.default_working_dir

        # 2) 相对路径 -> 以默认 cwd 为基准拼出来
        if not cwd.is_absolute():
            cwd = (self.default_working_dir / cwd).resolve()

        # 3) 不存在/不是目录 -> 回退默认 cwd
        if not cwd.exists() or not cwd.is_dir():
            cwd = self.default_working_dir

        return cwd

    def run_command(self, command: str, working_dir: Optional[str] = None) -> Tuple[bool, str, str]:
        cwd = self._normalize_cwd(working_dir)
        return self.skill_manager.parse_and_execute_command(command, working_dir=str(cwd))
