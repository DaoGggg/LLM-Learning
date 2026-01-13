from __future__ import annotations

from typing import Optional, Tuple

# 你现有的 SkillManager 里已经实现了：
# - extract_commands_from_text
# - parse_and_execute_command
# - venv python executable handling
# - special write_file handling
# 这些逻辑在你上传文件中已存在 :contentReference[oaicite:17]{index=17}

from skill_manager import SkillManager  # 或改成 from src.skills.skill_manager import SkillManager


class SkillExecutor:
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def run_command(self, command: str, working_dir: Optional[str] = None) -> Tuple[bool, str, str]:
        return self.skill_manager.parse_and_execute_command(command, working_dir=working_dir)
