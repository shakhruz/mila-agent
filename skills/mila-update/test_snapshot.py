#!/usr/bin/env python3
"""Снимок перед обновлением: что должно уцелеть (задания mila-cron, кроны сессии, хуки settings.json, навыки) — без значений;
health после обновления называет пропавшее. Песочница: свой дом, модуль грузится с MILA_HOME."""
import importlib.util, json, os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(name, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← %s" % str(x)[:200]))
T = tempfile.mkdtemp(prefix="snap-"); HOME = os.path.join(T, "home"); CL = os.path.join(HOME, ".claude"); W = os.path.join(HOME, "work")
for d in ("schedule", "state"): os.makedirs(os.path.join(W, d))
os.makedirs(os.path.join(CL, "skills", "dela")); os.makedirs(os.path.join(CL, "skills", "jev"))
open(os.path.join(CL, "skills", "dela", "SKILL.md"), "w").write("---\nname: dela\n---\n")
open(os.path.join(CL, "skills", "jev", "SKILL.md"), "w").write("---\nname: jev\n---\n")
SECRET = "sk-" + "or-" + "v1-zzzz9999"
json.dump({"version": 1, "jobs": [{"id": "utro", "cron": "0 9 * * *", "text": "Утренний план хозяину"}, {"id": "vecher", "cron": "0 20 * * *", "text": "Итог"}]},
          open(os.path.join(W, "schedule", "jobs.json"), "w"))
json.dump([{"cron": "17 10 * * *", "prompt": "Второй взгляд"}], open(os.path.join(W, "state", "crons.json"), "w"))
json.dump({"env": {"OPENROUTER_API_KEY": SECRET, "OWNER_ID": "555"}, "hooks": {"PreToolUse": [{"matcher": "x", "hooks": [{"type": "command", "command": "python3 $HOME/.claude/hooks/send-guard.py"}]}],
           "Stop": [{"hooks": [{"type": "command", "command": "python3 /h/.claude/hooks/reply-required.py"}]}]}}, open(os.path.join(CL, "settings.json"), "w"))
os.environ.update(MILA_HOME=HOME, CLAUDE_CONFIG_DIR=CL, MILA_WORK=W)
spec = importlib.util.spec_from_file_location("upd", os.path.join(H, "update.py")); U = importlib.util.module_from_spec(spec); spec.loader.exec_module(U)
p = U.snapshot("v9.9.9"); s = json.load(open(p)); raw = open(p).read()
chk("снимок: задания, кроны, хуки, навыки", s["jobs"] == ["utro", "vecher"] and len(s["crons"]) == 1 and "PreToolUse:send-guard.py" in s["hooks"] and set(s["skills"]) == {"dela", "jev"}, s)
chk("без значений: ни ключа из env, ни текстов задач и кронов", SECRET not in raw and "Утренний" not in raw and "Второй взгляд" not in raw and "555" not in raw)
chk("файл снимка 600", os.stat(p).st_mode & 0o777 == 0o600)
chk("ничего не пропало — health молчит", U.snapshot_lost(p) == [])
json.dump({"version": 1, "jobs": [{"id": "utro", "cron": "0 9 * * *", "text": "x"}]}, open(os.path.join(W, "schedule", "jobs.json"), "w"))
os.remove(os.path.join(W, "state", "crons.json")); shutil.rmtree(os.path.join(CL, "skills", "jev"))
cfg = json.load(open(os.path.join(CL, "settings.json"))); cfg["hooks"].pop("Stop"); json.dump(cfg, open(os.path.join(CL, "settings.json"), "w"))
lost = U.snapshot_lost(p); txt = " | ".join(lost)
chk("пропало задание vecher — названо", "задания расписания: 1 (vecher)" in txt, lost)
chk("пропали кроны сессии — названо", "кроны сессии: 1" in txt, lost)
chk("пропал хук Stop — назван", "Stop:reply-required.py" in txt, lost)
chk("пропал навык jev — назван", "навыки: jev" in txt, lost)
import time
os.makedirs(U.STATE, exist_ok=True); json.dump({"tag": "v9.9.9", "files": {}, "snapshot": p, "snapshot_ts": time.time()}, open(U.VERSION, "w"))
pr = U.run_health({}, "v9.9.9")
chk("health сразу после обновления: пропавшее из снимка — провал (ночной откатит)", any("задания расписания" in x for x in pr), pr)
json.dump({"tag": "v9.9.9", "files": {}, "snapshot": p, "snapshot_ts": time.time() - U.SNAP_FRESH - 60}, open(U.VERSION, "w"))
U.NOTES.clear(); pr = U.run_health({}, "v9.9.9")
chk("health через час: Мила могла снять задание сама — не провал, только заметка", not any("задания" in x for x in pr) and any("задания расписания" in x for x in U.NOTES), (pr, U.NOTES))
os.makedirs(os.path.join(CL, "skills", "old-name"))   # релиз переименовал: под старым именем алиас без SKILL.md
open(os.path.join(CL, "skills", "old-name", "SKILL.md"), "w").write("x"); pa = U.snapshot("v9.9.13"); os.remove(os.path.join(CL, "skills", "old-name", "SKILL.md"))
chk("переименованный релизом навык (алиас без SKILL.md) — не «пропал»", not any("old-name" in x for x in U.snapshot_lost(pa)), U.snapshot_lost(pa))
cfg = json.load(open(os.path.join(CL, "settings.json"))); cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "python3 /h/.claude/hooks/send-guard.py --strict"; json.dump(cfg, open(os.path.join(CL, "settings.json"), "w"))
chk("хук с аргументом: имя — файл, не «--strict»", "PreToolUse:send-guard.py" in json.load(open(U.snapshot("v9.9.14")))["hooks"])
# дом не верит: ссылка вместо jobs.json — не читается (снимок пустой по заданиям), чужой файл не тронут
out = os.path.join(T, "outside.json"); json.dump({"jobs": [{"id": "chuzhoe"}]}, open(out, "w"))
os.remove(os.path.join(W, "schedule", "jobs.json")); os.symlink(out, os.path.join(W, "schedule", "jobs.json"))
p2 = U.snapshot("v9.9.10"); chk("jobs.json — ссылка наружу: не читаю", json.load(open(p2))["jobs"] == [])
os.remove(os.path.join(W, "schedule", "jobs.json")); os.rmdir(os.path.join(W, "schedule"))
od = os.path.join(T, "outdir"); os.makedirs(od); json.dump({"jobs": [{"id": "chuzhoe"}]}, open(os.path.join(od, "jobs.json"), "w")); os.symlink(od, os.path.join(W, "schedule"))
p3 = U.snapshot("v9.9.11"); chk("папка schedule — ссылка наружу: не читаю", json.load(open(p3))["jobs"] == [])
chk("два снимка в одну секунду с тем же тегом — оба есть, второй рядом", U.snapshot("v9.9.12") != U.snapshot("v9.9.12"))
chk("снимка нет / испорчен — health не падает", U.snapshot_lost(os.path.join(T, "nope.json")) == [] and U.snapshot_lost(None) == [])
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
