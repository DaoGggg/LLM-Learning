
import os
from openai import OpenAI, api_key
from langgraph_ext.agent_factory import create_skill_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage




# 创建模型实例
llm = ChatOpenAI(
    model="qwen-plus",
    temperature=0.7,
    api_key="",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

agent = create_skill_agent(llm, "skills", ["file-size-classification","xhs-viral-title"])

result = agent.invoke({
    "messages": [HumanMessage(content="给我起一个skills教学的小红书标题")],
    "selected_skill": None,
    "skill_docs_injected": False,
})

print(result["messages"][-1].content)

