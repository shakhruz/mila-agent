#!/usr/bin/env python3
"""Every GitHub workflow parses as YAML and has jobs: a «: » inside an unquoted step name broke agent-image.yml once and the
workflow silently stopped running (the run showed only the file path as its name)."""
import glob, os, sys, yaml
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ok = n = 0
for f in sorted(glob.glob(os.path.join(R, ".github", "workflows", "*.yml"))):
    n += 1
    try:
        d = yaml.safe_load(open(f, encoding="utf-8")); good = isinstance(d, dict) and isinstance(d.get("jobs"), dict) and d.get("name")
    except yaml.YAMLError as e:
        good, d = False, e
    ok += bool(good); print(("✅ " if good else "❌ ") + os.path.basename(f) + ("" if good else "  ← " + str(d)[:200]))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
