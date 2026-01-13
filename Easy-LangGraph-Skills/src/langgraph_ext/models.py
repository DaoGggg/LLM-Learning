from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List


@dataclass(frozen=True)
class SkillMeta:
    name: str
    description: str
    skill_dir: Path
    skill_md_path: Path


@dataclass
class SkillRuntime:
    """Runtime cache + indices for a single skill."""
    meta: SkillMeta
    full_md: Optional[str] = None
    scripts: Dict[str, Path] = None  # script_name -> absolute path
    reference_files: List[Path] = None
