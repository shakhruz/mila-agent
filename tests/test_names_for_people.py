#!/usr/bin/env python3
"""Names people see: the schedule service is «Планировщик» / the Scheduler in every text a person or Mila reads (skills, docs,
READMEs, the cloud guides). The old name stays only in file names and state paths (install/baraban.py, state/baraban) and in the
history (CHANGELOG.md)."""
import os, re, subprocess, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = re.compile("Бара" + "бан|Bara" + "ban")   # glued: this file is a text too
files = [f for f in subprocess.run(["git", "ls-files"], cwd=R, capture_output=True, text=True).stdout.split()
         if f.endswith(".md") and f != "CHANGELOG.md" and not f.startswith("legacy/")]
hits = []
for f in files:
    try: t = open(os.path.join(R, f), encoding="utf-8").read()
    except OSError: continue
    hits += ["%s:%d" % (f, i) for i, l in enumerate(t.splitlines(), 1) if OLD.search(l)]
ok = not hits and len(files) > 20
print(("✅ " if ok else "❌ ") + "в текстах для людей (%d файлов .md) старого имени службы расписания нет%s" % (len(files), "" if ok else " — " + ", ".join(hits[:8])))
print("итог %d/1" % ok); sys.exit(0 if ok else 1)
