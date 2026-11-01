#!/usr/bin/env python3
"""No README carries a hand-written version number next to «latest»: a number there goes stale on the next release — release.sh
bumps release.json AFTER the tests, so a check «README = release.json» passed with v1.6.6 and the release shipped v1.7.0 with
«Latest: v1.6.6». The README links to releases/latest (and the badge reads the version itself)."""
import os, re, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = n = 0
for f in ("README.md", "README.ru.md", "README.uz.md", "README.zh-CN.md"):
    t = open(os.path.join(R, f), encoding="utf-8").read()
    stale = re.findall(r"releases/latest\)?\"?>?\]?\(?\s*(v\d+\.\d+\.\d+)", t) + re.findall(r"\[(v\d+\.\d+\.\d+)\]\(https://github\.com/[^)]*/releases/latest\)", t) \
        + re.findall(r'<a href="https://github\.com/[^"]*/releases/latest">(v\d+\.\d+\.\d+)</a>', t) + re.findall(r"(?i)latest:?\s*v\d+\.\d+\.\d+", t)
    n += 1; good = not stale and "releases/latest" in t; ok += good
    print(("✅ " if good else "❌ ") + "%s: ссылка на последний выпуск без числа версии%s" % (f, "" if good else " — найдено %s" % stale))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
