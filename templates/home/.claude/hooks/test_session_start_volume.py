#!/usr/bin/env python3
"""session-start.py (layout B, 09.11): keys/io not on a volume → once a day a line asking Mila to tell the owner in one card."""
import json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__))
ok = n = 0
def check(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="ss-vol-")
try:
    home = os.path.join(T, "home"); os.makedirs(home); sj = os.path.join(T, "state.json")
    def run(state):
        json.dump(state, open(sj, "w"))
        r = subprocess.run([sys.executable, "-I", os.path.join(H, "session-start.py")], env={"HOME": home, "MILA_STATE_JSON": sj, "PATH": "/usr/bin:/bin"},
                           capture_output=True, text=True, timeout=30)
        return r.stdout
    out = run({"persistent": False})
    check("нет тома → строка «скажи владельцу одной карточкой» с путём /var/lib/mila", "НЕ на постоянном томе" in out and "/var/lib/mila" in out, out)
    check("в тот же день второй старт — без напоминания", "НЕ на постоянном томе" not in run({"persistent": False}))
    open(os.path.join(home, "state", "no-volume-told"), "w").write("2000-01-01")
    check("на следующий день — снова", "НЕ на постоянном томе" in run({"persistent": False}))
    shutil.rmtree(os.path.join(home, "state"))
    check("том есть — ничего", "постоянном томе" not in run({"persistent": True}))
    os.unlink(sj)
    r = subprocess.run([sys.executable, "-I", os.path.join(H, "session-start.py")], env={"HOME": home, "MILA_STATE_JSON": sj, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=30)
    check("нет файла раскладки (не Mila Agent) — хук не падает, ничего про том", r.returncode == 0 and "томе" not in r.stdout, r.stderr)
    # owners.pending after the update (old io/ in the home is the fallback place when /var/lib/mila/io is absent here)
    io_ = os.path.join(home, ".claude", "channels", "telegram", "io"); os.makedirs(io_); open(os.path.join(io_, "owners.pending"), "w").close()
    out = run({"persistent": True})
    check("хозяин не определён → строка «скажи тому, с кем спарен: задайте OWNER_ID, согласия заново»", "OWNER_ID" in out and "согласия" in out, out)
    check("в тот же день — без повтора", "OWNER_ID" not in run({"persistent": True}))
    print("итог %d/%d" % (ok, n))
finally:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok == n else 1)
