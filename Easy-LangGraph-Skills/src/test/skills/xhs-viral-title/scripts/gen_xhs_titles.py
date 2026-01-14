
#!/usr/bin/env python3
import argparse
import json
import random
from collections import Counter

TEMPLATES = [
    ("数字清单", "{aud}必看！{topic}这{n}个技巧，真的{result}"),
    ("避坑", "{topic}千万别这么做：{n}个坑我替你踩过了"),
    ("对比", "{topic}对比：这样做{result}，那样做直接翻车"),
    ("结果导向", "做对这一步，{topic}立刻{result}（亲测有效）"),
    ("干货", "{topic}干货分享：{kws}一步到位的思路"),
    ("情绪共鸣", "我承认…{topic}让我{emotion}到不行"),
    ("经验总结", "{topic}我研究了{n}天，终于搞懂{result}"),
    ("强主张", "{topic}别再瞎忙了！正确做法其实很简单"),
    ("反常识", "{topic}最反常识的一点：越努力越{bad}"),
    ("人群定向", "{aud}看过来：{topic}这样做最{result}"),
]

RESULT_WORDS = ["显瘦", "高级感拉满", "省钱", "效率翻倍", "氛围感爆棚", "直接封神", "更耐看", "更好上手"]
EMOTIONS = ["安心", "激动", "心动", "崩溃", "治愈", "后悔", "上头"]
BAD_WORDS = ["费钱", "显土", "更焦虑", "越做越乱"]

def pick(lst):
    return random.choice(lst)

def build_titles(topic: str, audience: str, style: str, count: int, keywords: list[str]):
    # 简单按 style 过滤模板（保持简单）
    templates = TEMPLATES
    if style and style != "混合":
        if style == "清单":
            templates = [t for t in TEMPLATES if t[0] == "数字清单"]
        elif style == "避坑":
            templates = [t for t in TEMPLATES if t[0] == "避坑"]
        elif style == "对比":
            templates = [t for t in TEMPLATES if t[0] == "对比"]
        elif style == "干货":
            templates = [t for t in TEMPLATES if t[0] in ("干货", "经验总结", "强主张")]
        elif style == "情绪":
            templates = [t for t in TEMPLATES if t[0] == "情绪共鸣"]
        elif style == "结果导向":
            templates = [t for t in TEMPLATES if t[0] in ("结果导向", "人群定向")]

    used_types = []
    titles = []

    kws_text = "、".join([k.strip() for k in keywords if k.strip()]) if keywords else "提升效果"
    aud = audience.strip() if audience else "你"

    for _ in range(count):
        ttype, tpl = pick(templates)
        used_types.append(ttype)
        n = random.choice([3, 5, 7, 9, 10])
        title = tpl.format(
            topic=topic.strip(),
            aud=aud,
            n=n,
            kws=kws_text,
            result=pick(RESULT_WORDS),
            emotion=pick(EMOTIONS),
            bad=pick(BAD_WORDS),
        )
        titles.append(title)

    return titles, Counter(used_types)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--audience", default="")
    parser.add_argument("--style", default="混合")
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--keywords", default="")
    args = parser.parse_args()

    keywords = [x.strip() for x in args.keywords.split(",")] if args.keywords else []
    titles, stats = build_titles(args.topic, args.audience, args.style, args.count, keywords)

    out = {
        "topic": args.topic,
        "audience": args.audience,
        "style": args.style,
        "count": args.count,
        "keywords": keywords,
        "template_stats": dict(stats),
        "titles": titles,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
