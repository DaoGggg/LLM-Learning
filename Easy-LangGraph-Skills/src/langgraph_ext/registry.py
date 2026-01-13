from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import SkillMeta, SkillRuntime


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


class SkillRegistry:
    """
    Discovers skills in a Claude-compatible folder structure.
    - One folder per skill
    - SKILL.md with YAML frontmatter (name/description)
    - scripts/ optional
    - reference/ optional
    """

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, SkillRuntime] = {}

    def scan(self) -> None:
        if not self.skills_dir.exists():
            return

        for skill_folder in self.skills_dir.iterdir():
            if not skill_folder.is_dir():
                continue

            md_path = skill_folder / "SKILL.md"
            if not md_path.exists():
                continue

            meta = self._parse_frontmatter(md_path, skill_folder)
            if not meta:
                continue

            runtime = SkillRuntime(
                meta=meta,
                full_md=None,
                scripts=self._index_scripts(skill_folder),
                reference_files=self._index_reference(skill_folder),
            )
            self._skills[meta.name] = runtime

    def list(self) -> Iterable[SkillRuntime]:
        return self._skills.values()

    def get(self, skill_name: str) -> Optional[SkillRuntime]:
        return self._skills.get(skill_name)

    def subset(self, enabled_skills: list[str]) -> Dict[str, SkillRuntime]:
        return {k: v for k, v in self._skills.items() if k in set(enabled_skills)}

    def _parse_frontmatter(self, md_path: Path, skill_folder: Path) -> Optional[SkillMeta]:
        content = md_path.read_text(encoding="utf-8")
        fm = _FRONTMATTER_RE.match(content)
        if not fm:
            return None

        fm_text = fm.group(1)
        name_match = _NAME_RE.search(fm_text)
        desc_match = _DESC_RE.search(fm_text)
        if not name_match or not desc_match:
            return None

        return SkillMeta(
            name=name_match.group(1).strip(),
            description=desc_match.group(1).strip(),
            skill_dir=skill_folder,
            skill_md_path=md_path,
        )

    def _index_scripts(self, skill_folder: Path) -> Dict[str, Path]:
        scripts_dir = skill_folder / "scripts"
        if not scripts_dir.is_dir():
            return {}
        out: Dict[str, Path] = {}
        for p in scripts_dir.iterdir():
            if p.is_file():
                out[p.name] = p.resolve()
        return out

    def _index_reference(self, skill_folder: Path) -> list[Path]:
        # user要求 reference/；官方示例也可能叫 resources/。两者都支持。
        candidates = []
        for folder_name in ("reference", "resources"):
            ref_dir = skill_folder / folder_name
            if ref_dir.is_dir():
                candidates.extend([p.resolve() for p in ref_dir.rglob("*") if p.is_file()])
        return candidates
