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
# the tests workflow runs on branch pushes and pull requests, not on tag pushes: a tag repeats a commit main already tested, and the
# second run only competes for the macOS runner (11.11: two runs cancelled in the queue, reported to the owner as «failed»)
t = yaml.safe_load(open(os.path.join(R, ".github", "workflows", "tests.yml"), encoding="utf-8")); on = t.get("on", t.get(True))
push = on.get("push") if isinstance(on, dict) else None
n += 1; good = isinstance(push, dict) and push.get("branches") and "tags" not in push and "pull_request" in on; ok += bool(good)
print(("✅ " if good else "❌ ") + "tests.yml: push — только ветки (не теги), pull_request — на месте" + ("" if good else "  ← %r" % (on,)))
n += 1; good = set(t["jobs"]) >= {"run_all", "run_all_macos"} and not any(j.get("continue-on-error") for j in t["jobs"].values()); ok += bool(good)
print(("✅ " if good else "❌ ") + "tests.yml: оба задания на месте, ни одно не помечено «ошибка не считается»")
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
