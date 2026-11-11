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
# the release workflow: starts only from a strict vX.Y.Z tag, writes nothing by default, and the one job that can write runs after the gate
r = yaml.safe_load(open(os.path.join(R, ".github", "workflows", "release.yml"), encoding="utf-8")); on = r.get("on", r.get(True)); jobs = r["jobs"]
def check(name, good, x=""):
    global ok, n
    n += 1; ok += bool(good); print(("✅ " if good else "❌ ") + name + ("" if good else "  ← %r" % (x,)))
check("release.yml: запуск только пушем тега vX.Y.Z (не ветка, не pull request, не rc)", isinstance(on, dict) and set(on) == {"push"} and on["push"] == {"tags": ["v[0-9]+.[0-9]+.[0-9]+"]}, on)
check("release.yml: по умолчанию прав нет", r.get("permissions") == {}, r.get("permissions"))
check("release.yml: у ворот права только на чтение", jobs["gate"]["permissions"] == {"contents": "read", "actions": "read"}, jobs["gate"].get("permissions"))
writers = [k for k, j in jobs.items() if any(v == "write" for v in (j.get("permissions") or {}).values())]
check("release.yml: писать может одно задание — release, только contents, и только после ворот", writers == ["release"] and jobs["release"]["permissions"] == {"contents": "write"} and jobs["release"].get("needs") == "gate", (writers, jobs["release"].get("needs")))
steps = [s for j in jobs.values() for s in j["steps"]]; outs = [s for s in steps if "uses" in s]
check("release.yml: код ворот и сборщика берётся из main, токен в .git не остаётся, чужих действий нет",
      outs and all(s["uses"] == "actions/checkout@v4" and s["with"].get("ref") == "main" and s["with"].get("persist-credentials") is False and s["with"].get("fetch-depth") == 0 for s in outs), outs)
runs = "\n".join(s.get("run", "") for s in steps)
check("release.yml: ворота зовутся с проверкой тестов этого коммита и ожиданием", 'tools/release_gate.py "$TAG" --main origin/main --tests "$GITHUB_REPOSITORY" --wait' in runs and not any(j.get("continue-on-error") for j in jobs.values()) and not any(s.get("continue-on-error") for s in steps))
check("release.yml: имя тега и sha попадают в команды только через окружение, не подстановкой в текст команды", "${{" not in runs, [l for l in runs.split("\n") if "${{" in l])
check("release.yml: существующий выпуск не заменяется; файлы — из коммита тега тем же сборщиком", "nothing is changed or replaced" in runs and "--clobber" not in runs and 'git show "$SHA:install/get.sh"' in runs and "tools/release_files.py" in runs and "--verify-tag" in runs)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
