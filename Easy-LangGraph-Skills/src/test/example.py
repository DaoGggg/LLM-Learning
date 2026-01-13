from langgraph_ext.skill_manager import SkillManager


# ----------------------------
# 1) 你接真实模型时，替换这里
# ----------------------------
def fake_model_call(messages):
    """
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
    这里用规则模拟：
    - 第一次看到用户要统计文件大小 -> 选择 skill
    - 注入 skill docs 后 -> 输出 bash code block 命令
    - 拿到 tool output 后 -> 总结
    """
    last = messages[-1]["content"]

    # 如果刚收到用户需求
    if messages[-1]["role"] == "user":
        return "I will use the file-size-classification skill"

    # 如果系统注入了 skill docs（我们用一个特征判断）
    if "## 已加载技能:" in last or "## Loaded Skill:" in last:
        # 输出命令（注意：脚本名不带路径）
        return """```bash
python classify_files_by_size.py ./ --small-max-kb 64 --medium-max-kb 512 --max-files 300
```"""

    # 如果上一步是 tool 输出（我们简单用关键字判断）
    if messages[-1]["role"] == "assistant" and '"result"' in last:
        return "我已完成统计：small/medium/large 分桶结果如上。你可以告诉我是否需要导出为 CSV 或按扩展名再分组。"

    # 默认
    return "我需要更多信息。"

from pathlib import Path

def main():
    BASE_DIR = Path(__file__).resolve().parent
    SKILLS_DIR = BASE_DIR / "skills"

    sm = SkillManager(
        skill_dir=str(SKILLS_DIR),
        venv_path=str(BASE_DIR / ".venv"),  # 可选
        enabled_skills=["file-size-classification"],
    )

    # ----------------------------
    # 2) 初始化 messages（LangGraph 里就是 state.messages）
    # ----------------------------
    system_prompt = "你是一个有帮助的助手。\n" + sm.get_skill_summary_prompt()
    messages = [{"role": "system", "content": system_prompt}]

    # 用户问题
    user_q = "请帮我统计当前目录下文件大小分布，并按 small/medium/large 分桶输出。"
    messages.append({"role": "user", "content": user_q})

    # ----------------------------
    # 3) 第一次模型调用：选择 skill
    # ----------------------------
    model_out = fake_model_call(messages)
    messages.append({"role": "assistant", "content": model_out})
    print("ASSISTANT #1:\n", model_out, "\n")

    skill = sm.detect_skill_trigger(model_out)
    if not skill:
        print("模型未选择 skill，结束。")
        return

    # ----------------------------
    # 4) 系统注入：按需加载完整 SKILL.md（渐进披露）
    # ----------------------------
    payload = sm.build_skill_docs_payload(skill)
    messages.append({"role": "system", "content": payload})
    print("SYSTEM injected skill docs.\n")

    # ----------------------------
    # 5) 第二次模型调用：输出命令
    # ----------------------------
    model_out2 = fake_model_call(messages)
    messages.append({"role": "assistant", "content": model_out2})
    print("ASSISTANT #2:\n", model_out2, "\n")

    # 抽取命令并执行
    cmds = sm.extract_commands_from_text(model_out2)
    if not cmds:
        print("未抽取到命令，结束。")
        return

    for cmd in cmds:
        ok, out, err = sm.parse_and_execute_command(cmd, working_dir=".")
        tool_text = out if ok else (out + "\n" + err)
        # 将执行结果作为 assistant message 回给模型（LangGraph 里通常用 ToolMessage）
        messages.append({"role": "assistant", "content": tool_text})
        print("TOOL OUTPUT:\n", tool_text, "\n")

    # ----------------------------
    # 6) 第三次模型调用：总结结果
    # ----------------------------
    model_out3 = fake_model_call(messages)
    messages.append({"role": "assistant", "content": model_out3})
    print("ASSISTANT #3:\n", model_out3, "\n")


if __name__ == "__main__":
    main()
