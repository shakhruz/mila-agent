#!/usr/bin/env python3
"""mila_state.py: layouts, moving an old Railway home into <root>/home (one rename at a time, resume, clash → refuse),
folders by descriptor, persistence check. Root-only steps (chown to root) — in wall_probe. Usage: python3 test_mila_state.py"""
import os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import mila_state as S

ok = n = 0
def check(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:200]))
def refuses(f, *a):
    try: f(*a); return False
    except S.Refuse: return True
ME = os.getuid()
T = tempfile.mkdtemp(prefix="mila-state-")
try:
    L = S.layout({}); check("по умолчанию — тома: дом /home/agent, ключи и io в /var/lib/mila", L == {"kind": "volumes", "root": "/var/lib/mila", "home": "/home/agent", "keys": "/var/lib/mila/keys", "io": "/var/lib/mila/io"}, L)
    L = S.layout({"MILA_STATE": "data:/data"}); check("Railway: /data/home, /data/keys, /data/io", (L["home"], L["keys"], L["io"]) == ("/data/home", "/data/keys", "/data/io"), L)

    def old_home():
        r = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(r, ".claude", "projects")); os.makedirs(os.path.join(r, "work"))
        open(os.path.join(r, "work", "NOW.md"), "w").write("x"); open(os.path.join(r, ".bashrc"), "w").write("x"); return r
    r = old_home(); moved = S.move_old_home(r, ME)
    check("старый дом в корне тома → весь в home/, корень пуст", sorted(os.listdir(r)) == ["home"] and sorted(moved) == [".bashrc", ".claude", "work"]
          and os.path.exists(os.path.join(r, "home", "work", "NOW.md")), (os.listdir(r), moved))
    check("повторный старт — ничего не переносит", S.move_old_home(r, ME) == [])
    r = tempfile.mkdtemp(dir=T); check("пустой новый том — ничего не делает", S.move_old_home(r, ME) == [] and os.listdir(r) == [])
    r = old_home(); os.mkdir(os.path.join(r, "keys"))
    check("в старом доме своя keys/ — отказ, не слияние, ничего не тронуто", refuses(S.move_old_home, r, ME) and not os.path.exists(os.path.join(r, "home")) and os.path.exists(os.path.join(r, "work")))
    # a start that died halfway: marker present, some names already in home/
    r = old_home(); open(os.path.join(r, S.MARK), "w").close(); os.mkdir(os.path.join(r, "home")); os.rename(os.path.join(r, "work"), os.path.join(r, "home", "work"))
    moved = S.move_old_home(r, ME)
    check("обрыв посреди переноса — следующий старт доводит (метка снята)", sorted(os.listdir(r)) == ["home"] and sorted(moved) == [".bashrc", ".claude"]
          and sorted(os.listdir(os.path.join(r, "home"))) == [".bashrc", ".claude", "work"], (os.listdir(r), moved))
    r = old_home(); open(os.path.join(r, S.MARK), "w").close(); os.makedirs(os.path.join(r, "home", ".bashrc"))
    check("полупереехавший дом со столкновением имени — отказ", refuses(S.move_old_home, r, ME))
    r = tempfile.mkdtemp(dir=T); os.symlink(old_home(), os.path.join(r, "root-link"))
    check("корень тома — ссылка: отказ", refuses(S.move_old_home, os.path.join(r, "root-link"), ME))

    base = tempfile.mkdtemp(dir=T); S.own(os.path.join(base, "keys"), ME, ME, 0o700)
    check("own: новая папка 700 своего uid", oct(os.lstat(os.path.join(base, "keys")).st_mode & 0o7777) == "0o700")
    os.symlink(tempfile.mkdtemp(dir=T), os.path.join(base, "io"))
    check("own: io — ссылка → отказ", refuses(S.own, os.path.join(base, "io"), ME, ME, 0o2750))
    S.own(os.path.join(base, "io2"), ME, ME, 0o2750)
    check("own: io 2750 с setgid", oct(os.lstat(os.path.join(base, "io2")).st_mode & 0o7777) == "0o2750")
    if os.geteuid() != 0: print("ℹ️  чужой uid и chown корня на root — под root (wall_probe), тут не root")
    check("persistent: та же папка, что «/» → не постоянный том", S.persistent("/", "/") is False)
    print("итог %d/%d" % (ok, n))
finally:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok == n else 1)
