

import argparse
import json
from pathlib import Path

def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            # skip hidden dirs
            if p.name.startswith("."):
                # rglob 没有直接 prune，这里简单跳过目录本身即可
                continue
            continue
        if p.is_file():
            # skip hidden files if you want
            yield p

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--small-max-kb", type=int, default=128)
    parser.add_argument("--medium-max-kb", type=int, default=1024)
    parser.add_argument("--max-files", type=int, default=200)
    args = parser.parse_args()

    root = Path(args.directory).resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": f"Not a directory: {str(root)}"}, ensure_ascii=False))
        return

    small_max = args.small_max_kb * 1024
    medium_max = args.medium_max_kb * 1024

    buckets = {
        "small": {"count": 0, "total_bytes": 0, "files": []},
        "medium": {"count": 0, "total_bytes": 0, "files": []},
        "large": {"count": 0, "total_bytes": 0, "files": []},
    }

    seen = 0
    for f in iter_files(root):
        try:
            size = f.stat().st_size
        except Exception:
            continue

        if size <= small_max:
            b = "small"
        elif size <= medium_max:
            b = "medium"
        else:
            b = "large"

        buckets[b]["count"] += 1
        buckets[b]["total_bytes"] += size
        if len(buckets[b]["files"]) < 20:
            buckets[b]["files"].append({"path": str(f), "bytes": size})

        seen += 1
        if seen >= args.max_files:
            break

    out = {
        "directory": str(root),
        "thresholds": {
            "small_max_kb": args.small_max_kb,
            "medium_max_kb": args.medium_max_kb,
        },
        "result": buckets,
        "scanned_files": seen,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
