# LangGraph Skill 扩展组件 + Claude Skills 目录标准（中文说明）

本项目实现一套 **Claude 风格 Skills（技能）管理层**，并提供 **面向 LangGraph 的 Skill 运行时能力**。
核心遵循 **渐进披露（Progressive Disclosure）** 原则：

- **启动/扫描阶段**：只加载技能元数据（name/description、脚本索引等），不注入完整 SKILL.md
- **真正需要使用某个技能时**：才加载该技能的完整 `SKILL.md`（并附上脚本/参考文件清单）注入到 Agent 上下文

这样可以避免 prompt 过长、减少误触发，并更贴近 Claude 官方技能机制。

---

## 功能特性

- **Claude 官方 Skills 文件夹组织方式**
    - `skills/<skill_folder>/SKILL.md`（必须，且包含 YAML frontmatter：name/description）
    - 可选：
        - `scripts/`：可执行脚本（如 Python）
        - `reference/` 或 `resources/`：参考文件目录（仅列出文件清单供模型选择是否读取/使用）

- **渐进披露（按需加载）**
    - 扫描阶段只解析 YAML frontmatter（name/description）
    - 只有在调用 `build_skill_docs_payload()` 时，才读取并缓存完整 SKILL.md

- **脚本定位加速**
    - 扫描阶段建立脚本索引（script_name -> path），避免每次执行脚本都遍历目录
    - 支持 `enabled_skills`（只暴露/允许使用指定技能）

- **执行能力（保留原逻辑）**
    - 支持 `python <script>.py ...`
    - 优先使用 `.venv/bin/python`（若存在）
    - 保留 `run_fs_ops.py -c "..."`（write_file 类场景）特殊处理

- **面向 LangGraph 集成**
    - `get_skill_summary_prompt()`：生成元数据摘要 prompt（放入 system prompt）
    - `detect_skill_trigger()`：检测模型是否选择了某个 skill
    - `build_skill_docs_payload()`：生成注入消息（完整 SKILL.md + scripts/reference 清单）
    - `extract_commands_from_text()` + `parse_and_execute_command()`：抽取并执行命令


## Skill 文件夹规范（Claude 标准）

每个 Skill 必须是一个文件夹：
一个文件夹 = 一个 Skill
必须有 SKILL.md
SKILL.md 必须包含 YAML frontmatter，例如：
---

name: file-size-classification
description: 将文件按大小分桶并输出报告。

---
### 可选目录：
- scripts/：脚本文件
- reference/ 或 resources/：参考资料（可以是 md/json/图片等）

## 使用方式
1) 初始化 SkillManager（可限制技能集合）
```python
from SkillManager import SkillManager

sm = SkillManager(
skill_dir="skills",
venv_path=".venv",
enabled_skills=["file-size-classification", "pdf-reader"],
)

```

2) 生成技能元数据摘要 prompt（放入 Agent system prompt）
```python   
system_prompt = "你是一个有帮助的助手。\n" + sm.get_skill_summary_prompt()
```
3) 检测模型选择了哪个 skill

- 模型应严格输出：
```plaintext
I will use the <skill name> skill
```
- 随后：
```python
skill = sm.detect_skill_trigger(model_text)
if skill:
payload = sm.build_skill_docs_payload(skill)
```
4) 注入 Skill Docs Payload

- 把 payload 作为 system message 注入对话，使模型读取完整 SKILL.md（并看到 scripts/reference 清单）。

5) 抽取并执行命令
```python
   cmds = sm.extract_commands_from_text(model_text_with_codeblock)
   for cmd in cmds:
   ok, out, err = sm.parse_and_execute_command(cmd, working_dir=".")
   ```