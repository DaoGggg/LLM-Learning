"""
Skill Manager Module
====================

This module manages skills that can be dynamically loaded and used by agents.

Claude-style skill folder layout:
- skills/<skill_folder>/
    - SKILL.md (YAML frontmatter: name, description + full docs)
    - scripts/ (optional) executable scripts
    - reference/ or resources/ (optional) reference files

Design goals:
- Scan-time loads only metadata (name/description/path). Full SKILL.md is lazy-loaded.
- Script lookup is indexed at scan-time for fast resolution.
- Optional enabled_skills controls which skills are exposed/usable.
"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Iterable
import sys
from loguru import logger

def configure_logger(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, backtrace=False, diagnose=False)



_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)

# Strict selection protocol (recommended for avoiding accidental triggers)
_SKILL_SELECT_RE = re.compile(r"^I will use the (.+?) skill\s*$", re.IGNORECASE)


@dataclass
class SkillMetadata:
    """Metadata extracted from SKILL.md YAML frontmatter (lazy-load full docs)."""
    name: str
    description: str
    skill_path: Path
    md_path: Path

    # Lazy-loaded cache:
    _full_content: Optional[str] = None

    # Indexed assets:
    scripts: Dict[str, Path] = field(default_factory=dict)          # script_name -> abs path
    reference_files: List[Path] = field(default_factory=list)      # abs paths

    def load_full_content(self) -> str:
        """Lazy-load full SKILL.md content and cache it."""
        if self._full_content is None:
            self._full_content = self.md_path.read_text(encoding="utf-8")
        return self._full_content


class SkillManager:
    """
    Manages skill discovery, loading, and execution.

    - scan() discovers skills and indexes scripts/references.
    - get_skill_summary_prompt() exposes only enabled skills (if provided).
    - get_skill_full_content() lazy-loads full SKILL.md when needed.
    - parse_and_execute_command() runs python scripts with venv python when available.
    """

    def __init__(
            self,
            skill_dir: str = "skills",
            venv_path: Optional[str] = None,
            enabled_skills: Optional[List[str]] = None,
    ):
        self.skill_dir = Path(skill_dir)
        self.venv_path = Path(venv_path) if venv_path else Path(".venv")

        # name -> metadata
        self.skills: Dict[str, SkillMetadata] = {}

        # script_name -> abs path (optionally restricted by enabled skills at lookup time)
        self._script_index: Dict[str, Path] = {}

        # enabled skill set (None => all)
        self._enabled_skills: Optional[set[str]] = set(enabled_skills) if enabled_skills else None

        self._scan_skills()

    def _normalize_script_token(self, token: str) -> str:
        """把模型输出的脚本 token 归一化为 index key：只取文件名 + 补 .py"""
        token = (token or "").strip()
        token = Path(token).name  # 兼容 xhs-viral-title/scripts/xxx.py 这种输出
        if token and not token.lower().endswith(".py"):
            token += ".py"
        return token

    def _fuzzy_match_script(self, script_name: str) -> Optional[Tuple[str, Path]]:
        """
        在已索引脚本中做模糊匹配，只返回 index 里的脚本（安全）。
        返回: (best_name, best_path)
        """
        candidates: List[str] = list(self._script_index.keys())
        if not candidates:
            return None

        # 先对“去掉 .py 的 stem”也做一轮匹配，提升命中率
        name_stem = script_name[:-3] if script_name.lower().endswith(".py") else script_name
        stem_map = {k[:-3] if k.lower().endswith(".py") else k: k for k in candidates}

        # 先匹配完整文件名
        best = difflib.get_close_matches(script_name, candidates, n=1, cutoff=0.60)
        if best:
            k = best[0]
            return k, self._script_index[k]

        # 再匹配 stem（例如 generate_xhs_title vs gen_xhs_titles）
        best2 = difflib.get_close_matches(name_stem, list(stem_map.keys()), n=1, cutoff=0.55)
        if best2:
            k = stem_map[best2[0]]
            return k, self._script_index[k]

        return None

    def build_skill_docs_payload(
            self,
            skill_name: str,
            include_scripts: bool = True,
            include_reference: bool = True,
            max_reference_files: int = 200,
    ) -> Optional[str]:
        """
        Build a message payload containing:
        - Full SKILL.md (lazy-load recommended)
        - Scripts inventory (if indexed)
        - Reference inventory (if indexed)
        """
        full = self.get_skill_full_content(skill_name)
        if not full:
            return None

        parts: List[str] = [f"## Loaded Skill: {skill_name}\n\n", full.strip(), "\n\n"]

        # --- scripts inventory (works if you have meta.scripts indexed) ---
        if include_scripts:
            meta = self.skills.get(skill_name)
            scripts = getattr(meta, "scripts", None) if meta else None
            if isinstance(scripts, dict) and scripts:
                parts.append("### Scripts\n")
                for n in sorted(scripts.keys()):
                    parts.append(f"- {n}\n")
                parts.append("\n")

        # --- reference inventory (works if you have meta.reference_files indexed) ---
        if include_reference:
            meta = self.skills.get(skill_name)
            ref_files = getattr(meta, "reference_files", None) if meta else None
            if isinstance(ref_files, list) and ref_files:
                parts.append("### Reference files\n")
                shown = 0
                for p in sorted(ref_files, key=lambda x: str(x)):
                    if shown >= max_reference_files:
                        parts.append(f"- ...(truncated, total={len(ref_files)})\n")
                        break
                    try:
                        # prefer relative path under skill folder if possible
                        rel = str(Path(p).relative_to(meta.skill_path))
                    except Exception:
                        rel = str(p)
                    parts.append(f"- {rel}\n")
                    shown += 1
                parts.append("\n")

        parts.append("Follow the skill instructions. If you need to execute scripts, output tool commands accordingly.\n")
        return "".join(parts)
    # -------------------------
    # Public configuration
    # -------------------------
    def set_enabled_skills(self, enabled_skills: Optional[List[str]]) -> None:
        """Update enabled skills. None means all skills are enabled."""
        self._enabled_skills = set(enabled_skills) if enabled_skills else None

    def iter_enabled_skills(self) -> Iterable[SkillMetadata]:
        if self._enabled_skills is None:
            return self.skills.values()
        return (m for k, m in self.skills.items() if k in self._enabled_skills)

    # -------------------------
    # Scanning + indexing
    # -------------------------
    def _scan_skills(self) -> None:
        """Scan the skill directory and load all SKILL.md frontmatter, index scripts/references."""
        if not self.skill_dir.exists():
            logger.warning(f"Skill directory not found: {self.skill_dir}")
            return

        for skill_folder in self.skill_dir.iterdir():
            if not skill_folder.is_dir():
                continue

            skill_md_path = skill_folder / "SKILL.md"
            if not skill_md_path.exists():
                continue

            try:
                meta = self._parse_skill_md_frontmatter(skill_md_path, skill_folder)
                if not meta:
                    continue

                # Index scripts + references at scan-time
                meta.scripts = self._index_scripts(skill_folder)
                meta.reference_files = self._index_reference(skill_folder)

                self.skills[meta.name] = meta

                # Global script index (first-win; detect collisions)
                for script_name, script_path in meta.scripts.items():
                    if script_name in self._script_index and self._script_index[script_name] != script_path:
                        logger.warning(
                            f"Script name collision '{script_name}': "
                            f"{self._script_index[script_name]} vs {script_path}. "
                            f"Keeping the first one."
                        )
                        continue
                    self._script_index[script_name] = script_path

                logger.debug(f"Loaded skill metadata: {meta.name}")

            except Exception as e:
                logger.error(f"Failed to load skill from {skill_folder}: {e}")

    def _parse_skill_md_frontmatter(self, md_path: Path, skill_folder: Path) -> Optional[SkillMetadata]:
        """
        Parse SKILL.md to extract metadata (name/description) WITHOUT storing full content.
        Full docs are lazy-loaded via SkillMetadata.load_full_content().
        """
        content = md_path.read_text(encoding="utf-8")

        fm = _FRONTMATTER_RE.match(content)
        if not fm:
            logger.warning(f"No YAML frontmatter found in {md_path}")
            return None

        fm_text = fm.group(1)
        name_match = _NAME_RE.search(fm_text)
        desc_match = _DESC_RE.search(fm_text)

        if not name_match or not desc_match:
            logger.warning(f"Missing name or description in {md_path}")
            return None

        return SkillMetadata(
            name=name_match.group(1).strip(),
            description=desc_match.group(1).strip(),
            skill_path=skill_folder,
            md_path=md_path,
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

    def _index_reference(self, skill_folder: Path) -> List[Path]:
        files: List[Path] = []
        for folder_name in ("reference", "resources"):
            ref_dir = skill_folder / folder_name
            if ref_dir.is_dir():
                files.extend([p.resolve() for p in ref_dir.rglob("*") if p.is_file()])
        return files

    # -------------------------
    # Prompt helpers
    # -------------------------
    def get_skill_summary_prompt(self, enabled_skills: Optional[List[str]] = None) -> str:
        """
        Generate a summary prompt containing skill metadata.
        If enabled_skills is provided, it overrides the manager's enabled set.
        """
        if not self.skills:
            return ""

        enabled_set: Optional[set[str]]
        if enabled_skills is not None:
            enabled_set = set(enabled_skills)
        else:
            enabled_set = self._enabled_skills

        def _iter_items():
            if enabled_set is None:
                return self.skills.items()
            return ((k, v) for k, v in self.skills.items() if k in enabled_set)

        prompt_parts = [
            "\n## Available Skills\n",
            "You are equipped with the following specialized skills. "
            "When a task aligns with a specific skill, adopt the methodology described within that skill. "
            "For tasks that do not fall under any specific skill, proceed by using your own reasoning and inherent knowledge.\n",
        ]

        for skill_name, metadata in _iter_items():
            prompt_parts.append(f"\n- **{skill_name}**: {metadata.description}")

        prompt_parts.append(
            "\n\n### Skill Usage Protocol\n\n"
            "When you identify that a task requires a skill:\n"
            "1. Respond EXACTLY with: 'I will use the <skill name> skill' and stop immediately.\n"
            "2. The full skill documentation will be provided to you automatically.\n"
            "3. After reviewing the documentation, output commands using one of these formats:\n\n"
            "**Format - Code Block:**\n"
            "```bash\n"
            "python script.py /path/to/directory --arg1 value1 --arg2 value2\n"
            "```\n\n"
            "**Important Notes:**\n"
            "- Commands will be executed automatically and their output will be provided back to you.\n"
            "- Do NOT output ANY commands in the same message where you select the skill.\n"
            "- When executing Python scripts, use the script name directly without path prefixes "
            "(e.g., 'python script.py' not 'python /path/to/script.py'). The system will locate the script automatically.\n"
        )

        return "".join(prompt_parts)

    def detect_skill_trigger(self, text: str) -> Optional[str]:
        """
        Detect whether the agent selected a skill.
        Prefer strict protocol: 'I will use the <skill name> skill'.
        Falls back to legacy substring checks (but only among enabled skills).
        """
        text = (text or "").strip()

        # 1) Strict protocol match
        m = _SKILL_SELECT_RE.match(text)
        if m:
            candidate = m.group(1).strip()
            if candidate in self.skills and self._is_skill_enabled(candidate):
                return candidate

        # 2) Backward-compatible fuzzy detection (enabled-only)
        text_lower = text.lower()
        for skill_name in self._enabled_skill_names():
            if skill_name.lower() in text_lower:
                return skill_name
            normalized = skill_name.replace("-", " ").replace("_", " ")
            if normalized.lower() in text_lower:
                return skill_name

        return None

    def _enabled_skill_names(self) -> List[str]:
        if self._enabled_skills is None:
            return list(self.skills.keys())
        return [k for k in self.skills.keys() if k in self._enabled_skills]

    def _is_skill_enabled(self, skill_name: str) -> bool:
        return self._enabled_skills is None or skill_name in self._enabled_skills

    # -------------------------
    # Lazy-load full SKILL.md
    # -------------------------
    def get_skill_full_content(self, skill_name: str) -> Optional[str]:
        """Lazy-load full SKILL.md content for a specific skill."""
        if not self._is_skill_enabled(skill_name):
            return None
        metadata = self.skills.get(skill_name)
        if not metadata:
            return None
        return metadata.load_full_content()

    # -------------------------
    # Script resolution
    # -------------------------
    def _locate_skill_script(self, script_name: str) -> Optional[Path]:
        """
        Locate a skill script by name using the scan-time index.
        If enabled skills are set, ensures the resolved script belongs to an enabled skill.
        """
        p = self._script_index.get(script_name)
        if not p:
            logger.warning(f"Script '{script_name}' not found in script index")
            return None

        # If enabled_skills is set, verify the script is under an enabled skill folder.
        if self._enabled_skills is not None:
            try:
                # skills/<skill_folder>/scripts/<script>
                # We map by checking which SkillMetadata has this script.
                for skill_name in self._enabled_skill_names():
                    meta = self.skills.get(skill_name)
                    if meta and meta.scripts.get(script_name) == p:
                        return p
                logger.warning(f"Script '{script_name}' is not in any enabled skill")
                return None
            except Exception:
                # If anything goes wrong, fail safe
                return None

        return p

    # -------------------------
    # Command execution (kept mostly as-is)
    # -------------------------
    def parse_and_execute_command(
            self,
            command: str,
            working_dir: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Parse and execute a command from the model's output.
        Handles Python commands with automatic venv environment.
        """
        command = command.strip()

        cwd = Path(working_dir) if working_dir else Path.cwd()

        logger.debug(f"Executing command: {command}")
        logger.debug(f"Working directory: {cwd}")

        try:
            if command.startswith("python "):
                success, stdout, stderr = self._execute_python_command(command, cwd)
            else:
                # Execute as shell command. We do not use this in this project.
                success, stdout, stderr = self._execute_shell_command(command, cwd)

            return success, stdout, stderr

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return False, "", str(e)



    def _resolve_venv_python(self) -> str:
        """
        Return python executable path for the configured venv (default .venv).
        Cross-platform (Windows / macOS / Linux). Falls back to current interpreter.
        """
        project_root = Path(__file__).parent.parent  # 与你现有逻辑保持一致
        venv_root = project_root / self.venv_path

        # Windows: .venv/Scripts/python.exe
        if os.name == "nt":
            cand = venv_root / "Scripts" / "python.exe"
            if cand.exists():
                return str(cand)
            cand = venv_root / "Scripts" / "python"
            if cand.exists():
                return str(cand)
        else:
            # POSIX: .venv/bin/python
            cand = venv_root / "bin" / "python"
            if cand.exists():
                return str(cand)

        # 最稳的 fallback：当前进程解释器
        return sys.executable or "python"

    def _execute_python_command(self, command: str, cwd: Path) -> Tuple[bool, str, str]:
        """
        Execute a Python command with venv activation.
        Automatically locates skill scripts in the skill directory.
        """
        import shlex

        # Special handling for run_fs_ops.py -c "..." commands containing write_file
        if "run_fs_ops.py" in command and " -c " in command and "write_file" in command:
            return self._execute_write_file_command(command, cwd)

        try:
            parts = shlex.split(command)
        except ValueError as e:
            logger.error(f"Failed to parse command: {command}, error: {e}")
            return False, "", f"Failed to parse command: {e}"

        if len(parts) < 2:
            logger.error(f"Invalid python command format: {command}")
            return False, "", "Invalid command format"

        script_name_raw = parts[1]
        script_name = self._normalize_script_token(script_name_raw)

        script_path = self._locate_skill_script(script_name)
        script_args = parts[2:] if len(parts) > 2 else []

        # ✅ 自动纠错：精确找不到就模糊匹配
        if not script_path:
            guess = self._fuzzy_match_script(script_name)
            if guess:
                guessed_name, guessed_path = guess
                logger.warning(
                    f"Script '{script_name_raw}' not found. Auto-correct to '{guessed_name}'."
                )
                script_path = guessed_path
            else:
                available = ", ".join(sorted(self._script_index.keys()))
                return False, "", (
                    f"Could not locate script: {script_name_raw}. "
                    f"Available scripts: {available}"
                )

        # 后面继续用 script_path 执行
        python_executable = self._resolve_venv_python()
        shell_cmd = [python_executable, str(script_path)] + script_args
        return self._run_subprocess(shell_cmd, cwd)

    def _execute_write_file_command(self, command: str, cwd: Path) -> Tuple[bool, str, str]:
        """
        Special handler for run_fs_ops.py -c "..." commands.
        Manual parsing to extract the -c argument safely.
        """
        script_path = self._locate_skill_script("run_fs_ops.py")
        if not script_path:
            logger.error("Could not locate run_fs_ops.py")
            return False, "", "Script not found: run_fs_ops.py"

        c_flag_pos = command.find(" -c ")
        if c_flag_pos == -1:
            logger.error("Could not find -c flag in run_fs_ops.py command")
            return False, "", "Invalid run_fs_ops.py command format"

        after_c = command[c_flag_pos + 4:].strip()
        if not after_c:
            logger.error("No argument found after -c flag")
            return False, "", "No argument after -c flag"

        quote_char = after_c[0]
        if quote_char not in ('"', "'"):
            code_arg = after_c
        else:
            code_arg = self._extract_quoted_string(after_c, quote_char)
            if code_arg is None:
                logger.error("Could not extract quoted argument from -c flag")
                return False, "", "Failed to parse -c argument"

        logger.debug(f"Extracted -c argument (length={len(code_arg)})")

        project_root = Path(__file__).parent.parent
        venv_activate = project_root / self.venv_path / "bin" / "activate"

        if venv_activate.exists():
            python_executable = project_root / self.venv_path / "bin" / "python"
            if not python_executable.exists():
                python_executable = "python"
        else:
            python_executable = "python"

        shell_cmd = [str(python_executable), str(script_path), "-c", code_arg]
        logger.debug("Executing fs_ops command with -c argument")
        logger.debug(f"Working directory: {cwd}")

        return self._run_subprocess(shell_cmd, cwd)

    def _extract_quoted_string(self, s: str, quote_char: str) -> Optional[str]:
        """Extract quoted string content, preserving escapes (best-effort)."""
        if not s or s[0] != quote_char:
            return None

        result: List[str] = []
        i = 1
        while i < len(s):
            char = s[i]
            if char == "\\" and i + 1 < len(s):
                result.append(char)
                result.append(s[i + 1])
                i += 2
            elif char == quote_char:
                return "".join(result)
            else:
                result.append(char)
                i += 1

        logger.warning("No closing quote found, using best-effort extraction")
        return "".join(result)

    def _execute_shell_command(self, command: str, cwd: Path) -> Tuple[bool, str, str]:
        shell_cmd = ["/bin/bash", "-c", command]
        return self._run_subprocess(shell_cmd, cwd)

    def _run_subprocess(self, cmd: list[str], cwd: Path):
        try:
            cwd = Path(cwd).resolve()
            if not cwd.exists() or not cwd.is_dir():
                cwd = Path.cwd().resolve()

            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",      # ✅ 强制 UTF-8
                errors="replace",      # ✅ 解码失败也不崩，替换为 �
                timeout=300,
            )
            ok = result.returncode == 0
            return ok, result.stdout or "", result.stderr or ""
        except subprocess.TimeoutExpired:
            return False, "", "命令执行超时（300 秒）"
        except Exception as e:
            # ✅ 任何异常也保证返回 str
            return False, "", f"Subprocess failed: {e}"
    # -------------------------
    # Command extraction (kept as-is)
    # -------------------------
    def _check_quotes_balanced(self, s: str) -> bool:
        in_single_quote = False
        in_double_quote = False
        i = 0

        while i < len(s):
            char = s[i]
            if char == "\\" and i + 1 < len(s):
                i += 2
                continue

            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote

            i += 1

        return not in_single_quote and not in_double_quote

    def extract_commands_from_text(self, text: str) -> List[str]:
        """
        Extract command strings from model output.
        Code blocks with bash/shell/python/sh tags.
        """
        import shlex

        command: List[str] = []

        def extract_commands_from_code(code: str) -> List[str]:
            result: List[str] = []
            lines = code.split("\n")
            current_command: List[str] = []
            in_quotes = False

            for line in lines:
                stripped = line.strip()

                if not in_quotes:
                    if not stripped or stripped.startswith("#"):
                        continue

                if current_command:
                    current_command.append(line)
                else:
                    current_command.append(stripped)

                full_cmd = "\n".join(current_command)

                if "fs.write_file" in full_cmd or "write_file" in full_cmd:
                    if self._check_quotes_balanced(full_cmd):
                        complete_cmd = full_cmd.strip()
                        if complete_cmd:
                            result.append(complete_cmd)
                        current_command = []
                        in_quotes = False
                    else:
                        in_quotes = True
                else:
                    try:
                        shlex.split(full_cmd)
                        complete_cmd = full_cmd.strip()
                        if complete_cmd:
                            result.append(complete_cmd)
                        current_command = []
                        in_quotes = False
                    except ValueError:
                        in_quotes = True

            if current_command:
                complete_cmd = "\n".join(current_command).strip()
                if complete_cmd:
                    result.append(complete_cmd)

            return result

        code_block_pattern = r"```(?:bash|shell|python|sh)\s*\n(.*?)```"
        match = re.search(code_block_pattern, text or "", re.DOTALL)
        if match:
            code = match.group(1).strip()
            command = extract_commands_from_code(code)

        if command:
            logger.debug(f"Extracted {len(command)} command(s) from text")
        else:
            logger.debug("No commands extracted from text")

        return command
