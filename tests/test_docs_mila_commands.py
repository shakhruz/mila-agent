#!/usr/bin/env python3
"""Every command that `mila help` names is named in docs/REFERENCE.md: a command added to the launcher without a line in the
reference fails here, so the page cannot fall behind the launcher again. Run: python3 tests/test_docs_mila_commands.py"""
import os, re, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(R, "install", "mila"), encoding="utf-8").read()
ref = open(os.path.join(R, "docs", "REFERENCE.md"), encoding="utf-8").read()
m = re.search(r"<<'HELP'\n(.*?)\nHELP\n", src, re.S)
cmds = sorted(set(re.findall(r"^mila ([a-z]+)\b", m.group(1), re.M))) if m else []
ok = n = 0
def chk(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
chk("в справке запускалки найдены команды (не меньше 20)", len(cmds) >= 20, cmds)
missing = [c for c in cmds if not re.search(r"`mila %s\b" % c, ref)]
chk("каждая команда из `mila help` названа в docs/REFERENCE.md", not missing, missing)
chk("в справочнике нет старого «`mila` resumes»", "`mila` resumes" not in ref)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
