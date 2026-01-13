---
name: file-size-classification
description: 将指定目录下的文件按大小分桶并输出统计结果（小/中/大）。
---

# file-size-classification

## When to use
- 用户需要统计某个目录下文件数量与大小分布
- 需要按大小分桶（例如 small/medium/large）生成报告

## Inputs
- directory: 需要扫描的目录
- thresholds:
    - small_max_kb: 小文件上限（KB）
    - medium_max_kb: 中文件上限（KB），大于该值视为 large

## Output
- JSON 输出，包含：每个桶的文件数、总大小、文件列表（最多列出前 N 个）

## How to execute
使用 scripts 中的脚本：

```bash
python classify_files_by_size.py <directory> --small-max-kb 128 --medium-max-kb 1024 --max-files 200
 ```
## Notes
- 不要递归到隐藏系统目录（可忽略以 . 开头的文件夹）
- 仅对普通文件统计