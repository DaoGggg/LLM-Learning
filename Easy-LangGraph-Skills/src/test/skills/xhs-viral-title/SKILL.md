---
name: xhs-viral-title
description: 根据主题与人群画像，生成10-20个高点击的小红书爆款标题（含不同标题模板风格）。
---

# xhs-viral-title

## When to use
- 用户想为小红书笔记生成高点击标题
- 需要多种风格（干货/对比/避坑/清单/情绪共鸣/结果导向）

## Inputs
- topic: 内容主题（必填）
- audience: 目标人群（可选）
- style: 风格偏好（可选：干货、避坑、对比、清单、情绪、结果导向、混合）
- count: 生成数量（默认 15）
- keywords: 关键词（可选，多个用逗号分隔）

## Output
- JSON：包含标题列表、使用的模板类型统计

## How to execute
使用脚本生成标题：
- 必须使用 Scripts 列表中的脚本名，禁止自行编造。

```bash
python gen_xhs_titles.py --topic "通勤穿搭" --audience "上班族女生" --style "混合" --count 15 --keywords "显瘦,高级感,平价"
```

## Guidelines
- 标题要短、强信息密度、可读性高
- 适当使用：数字、情绪词、结果词、对比结构、避坑结构
- 不要夸大承诺，不要违规词
