from __future__ import annotations

from typing import Optional, Tuple

from skill_manager import SkillManager

class SkillExecutor:
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def run_command(self, command: str, working_dir: Optional[str] = None) -> Tuple[bool, str, str]:
        return self.skill_manager.parse_and_execute_command(command, working_dir=working_dir)
