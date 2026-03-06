#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把标准 JSON 转成适合命令行 --arg 使用的单行、已转义字符串。
用于处理大 JSON（如 flight.createOrder 的 goExtData 等）的转义问题，无需每次手写 JSON 文件。

用法:
  从文件读取:
    python3 scripts/json_arg_escape.py path/to/payload.json

  从 stdin 读取（可粘贴或管道）:
    python3 scripts/json_arg_escape.py < payload.json
    echo '{"a":1}' | python3 scripts/json_arg_escape.py

输出: 一行单引号包裹的字符串，可直接作为 apiexe.py --arg 的参数。
"""

import sys
import json
from pathlib import Path

# 脚本所在目录的父目录为 skill 根目录
SCRIPT_DIR = Path(__file__).resolve().parent


def load_json():
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        path = Path(raw)
        if not path.is_absolute() and not path.exists():
            path = SCRIPT_DIR.parent / raw
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    text = sys.stdin.read()
    if not text.strip():
        print("Usage: json_arg_escape.py [json_file]  or  stdin", file=sys.stderr)
        sys.exit(1)
    return json.loads(text)


def shell_single_quoted(s: str) -> str:
    """转成适合单引号包裹的 shell 字符串：' 变成 '\'' """
    return "'" + s.replace("'", "'\"'\"'") + "'"


def main():
    try:
        data = load_json()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    print(shell_single_quoted(s))


if __name__ == "__main__":
    main()
