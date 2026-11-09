#!/usr/bin/env python3
"""audit №5/№6: the entrypoint's root step starts with «cd /», every python3 it runs as root has -I, cards.jsonl goes through
own-file (by descriptor). Exit 0 — fine; 1 — the offending lines. Usage: python3 check_root_python.py docker/entrypoint.sh"""
import re, sys
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
start = next(i for i, l in enumerate(lines) if l.startswith('if [ "$(id -u)" = 0 ]; then'))
end = next(i for i in range(start + 1, len(lines)) if lines[i] == "fi")
block = lines[start + 1:end]
bad = []
if not block or not block[0].strip().startswith("cd / "): bad.append("first line is not «cd /»: %s" % (block[0] if block else ""))
for i, l in enumerate(block, start + 2):
    if "setpriv --reuid=mila-io" in l or "setpriv --reuid=mila-guest" in l: break   # from here on: other users, not root
    code = re.split(r"\s#\s", l, maxsplit=1)[0]   # a trailing comment is prose, not a command
    for m in re.finditer(r"\bpython3\b(?!\S)", code):
        if not re.match(r"\s+-I\b", code[m.end():]) and "MILA_STATE_CMD" not in code: bad.append("%d: python3 without -I: %s" % (i, l.strip()[:120]))
if not any("own-file" in l and "cards.jsonl" in l for l in block): bad.append("cards.jsonl is not made by own-file")
if any(re.search(r"\b(touch|chown|chmod)\b[^#]*cards\.jsonl", l) for l in block): bad.append("cards.jsonl still touched/chown/chmod by path")
print("\n".join(bad) or "ok"); sys.exit(1 if bad else 0)
