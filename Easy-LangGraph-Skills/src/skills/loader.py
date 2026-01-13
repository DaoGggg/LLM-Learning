from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .models import SkillRuntime


class SkillLoader:
    def __init__(self, runtimes: Dict[str, SkillRuntime]):
        self.runtimes = runtimes

    def build_skill_summaries(self) -> str:
        if not self.runtimes:
            return ""

        lines = ["\n## Available Skills\n"]
        for name, rt in self.runtimes.items():
            lines.append(f"- **{name}**: {rt.meta.description}")
        lines.append(
            "\n\n### Skill Usage Protocol\n"
            "When a task requires a skill, respond EXACTLY with:\n"
            "`I will use the <skill name> skill`\n"
            "Do not output commands in the same message.\n"
        )
        return "\n".join(lines)

    def load_full_skill_markdown(self, skill_name: str) -> Optional[str]:
        rt = self.runtimes.get(skill_name)
        if not rt:
            return None
        if rt.full_md is None:
            rt.full_md = rt.meta.skill_md_path.read_text(encoding="utf-8")
        return rt.full_md

    def build_reference_inventory(self, skill_name: str) -> str:
        rt = self.runtimes.get(skill_name)
        if not rt:
            return ""
        if not rt.reference_files:
            return "Reference files: (none)\n"
        rels = []
        for p in rt.reference_files:
            try:
                rels.append(str(p.relative_to(rt.meta.skill_dir)))
            except Exception:
                rels.append(str(p))
        rels_sorted = sorted(rels)
        return "Reference files:\n" + "\n".join([f"- {x}" for x in rels_sorted]) + "\n"

    def build_scripts_inventory(self, skill_name: str) -> str:
        rt = self.runtimes.get(skill_name)
        if not rt:
            return ""
        if not rt.scripts:
            return "Scripts: (none)\n"
        names = sorted(rt.scripts.keys())
        return "Scripts:\n" + "\n".join([f"- {n}" for n in names]) + "\n"
