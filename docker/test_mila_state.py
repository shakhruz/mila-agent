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
    L = S.layout({}); check("по умолчанию (решение Б) — один том /var/lib/mila: home, keys, io внутри", L == {"kind": "data", "root": "/var/lib/mila", "home": "/var/lib/mila/home", "keys": "/var/lib/mila/keys", "io": "/var/lib/mila/io"}, L)
    L = S.layout({"MILA_STATE": "volumes"}); check("volumes — старый дом /home/agent (для тех, кто не сменил точку монтирования)", L["home"] == "/home/agent", L)
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
    # stand 10.11: the runtime made an empty home/ (the image's WORKDIR) inside the old volume before the entrypoint
    r = old_home(); os.mkdir(os.path.join(r, "home")); moved = S.move_old_home(r, ME)
    check("стенд 10.11: пустой home/ от среды запуска — старый дом всё равно переезжает", sorted(os.listdir(r)) == ["home"]
          and sorted(moved) == [".bashrc", ".claude", "work"] and os.path.exists(os.path.join(r, "home", "work", "NOW.md")), (os.listdir(r), moved))
    r = old_home(); os.makedirs(os.path.join(r, "home", "work")); open(os.path.join(r, "home", "work", "NOW.md"), "w").write("y")
    check("старый дом в корне и home/ с файлами — отказ вслух, ничего не тронуто", refuses(S.move_old_home, r, ME)
          and os.path.exists(os.path.join(r, "work", "NOW.md")) and open(os.path.join(r, "home", "work", "NOW.md")).read() == "y")
    r = old_home(); os.symlink(tempfile.mkdtemp(dir=T), os.path.join(r, "home"))
    check("старый дом и home — ссылка: отказ", refuses(S.move_old_home, r, ME) and os.path.exists(os.path.join(r, "work")))

    # Claude finds memory by the folder named after the path: a moved home renames -home-agent… to the new prefix
    hm = tempfile.mkdtemp(dir=T); pj = os.path.join(hm, ".claude", "projects"); new = S.slug(hm)
    for d in ("-home-agent", "-home-agent-work", "-home-agent-work-drafts-x", "-tmp-other", new + "-work-drafts-x"):
        os.makedirs(os.path.join(pj, d, "memory"))
    open(os.path.join(pj, "-home-agent-file"), "w").close(); os.makedirs(os.path.join(pj, "-home-agentX"))
    done = S.rename_projects(hm)
    names = set(os.listdir(pj))
    check("папки памяти: -home-agent… → новый путь дома", {new, new + "-work"} <= names and "-home-agent" not in names and "-home-agent-work" not in names, sorted(names))
    check("столкновение имени — обе папки остаются как были", "-home-agent-work-drafts-x" in names and new + "-work-drafts-x" in names)
    check("чужие (-tmp-other, -home-agentX) и не папки не тронуты", {"-tmp-other", "-home-agentX", "-home-agent-file"} <= names)
    check("повтор — ничего не переименовывает", S.rename_projects(hm) == [])
    check("дом без .claude — тихо пусто", S.rename_projects(tempfile.mkdtemp(dir=T)) == [])
    # io/ out of the home (№9): journals carried, decisions to quarantine only, owners/hmac never
    sys.path.insert(0, os.path.join(H, "..", "consent")); import decisions as DC
    def old_io():
        hm = tempfile.mkdtemp(dir=T); oi = os.path.join(hm, ".claude", "channels", "telegram", "io"); os.makedirs(os.path.join(oi, "consent"))
        open(os.path.join(oi, "events.jsonl"), "w").write('{"e":1}\n'); open(os.path.join(oi, "taps.jsonl"), "w").write('{"t":1}\n')
        open(os.path.join(oi, "owners.json"), "w").write('{"owners": ["666"]}'); open(os.path.join(oi, "consent", "hmac.key"), "wb").write(b"k" * 32)
        DC.append(os.path.join(oi, "consent", "decisions.jsonl"), {"verdict": "granted", "act": "post"})
        nio = tempfile.mkdtemp(dir=T); return hm, oi, nio
    ver = lambda p: DC.verify(p)[0]
    hm, oi, nio = old_io(); r = S.migrate_io(hm, nio, ME, ME, ver)
    got = sorted(os.listdir(nio))
    check("io: журналы перенесены, владельцы и ключ подписи — нет", {"events.jsonl", "taps.jsonl"} <= set(got) and "owners.json" not in got and not os.path.exists(os.path.join(nio, "consent", "hmac.key")), got)
    check("io: решения владельца — только в карантин (цепочка без секрета), рабочего журнала нет", r["decisions"] == "quarantine (chain intact)" and os.path.exists(os.path.join(nio, "quarantine", "decisions.jsonl")) and not os.path.exists(os.path.join(nio, "consent", "decisions.jsonl")), r)
    check("io: повтор — ничего не делает (метка .migrated в io/)", S.migrate_io(hm, nio, ME, ME, ver) == {"skipped": True})
    hm, oi, nio = old_io(); open(os.path.join(oi, "consent", "decisions.jsonl"), "a").write('{"n": 9, "verdict": "granted"}\n')
    check("io: подделанная цепочка — тоже карантин, с пометкой «broken»", S.migrate_io(hm, nio, ME, ME, ver)["decisions"] == "quarantine (chain broken)")
    hm, oi, nio = old_io(); os.unlink(os.path.join(oi, "events.jsonl")); v = os.path.join(T, "victim-ev"); open(v, "w").write("SECRET"); os.symlink(v, os.path.join(oi, "events.jsonl"))
    os.unlink(os.path.join(oi, "taps.jsonl")); v2 = os.path.join(T, "victim-hl"); open(v2, "w").write("SECRET2"); os.link(v2, os.path.join(oi, "taps.jsonl"))
    S.migrate_io(hm, nio, ME, ME, ver)
    check("io: журнал-ссылка и журнал — жёсткая ссылка не переносятся", not os.path.exists(os.path.join(nio, "events.jsonl")) and not os.path.exists(os.path.join(nio, "taps.jsonl")))
    hm = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(hm, ".claude", "channels", "telegram")); real = tempfile.mkdtemp(dir=T)
    open(os.path.join(real, "events.jsonl"), "w").write("x"); os.symlink(real, os.path.join(hm, ".claude", "channels", "telegram", "io")); nio = tempfile.mkdtemp(dir=T)
    r = S.migrate_io(hm, nio, ME, ME, ver)
    check("io: старая io/ — ссылка: ничего не переносится, метка ставится", r["journals"] == [] and os.path.exists(os.path.join(nio, ".migrated")), r)
    # №6: a file root makes in the session's folder — never through what the session left there
    tg = tempfile.mkdtemp(dir=T); vic = os.path.join(T, "victim-cards"); open(vic, "w").write("ROOT"); os.chmod(vic, 0o600)
    os.symlink(vic, os.path.join(tg, "cards.jsonl")); S.own_file(tg, "cards.jsonl", ME, ME, 0o660)
    check("own_file: ссылка на месте cards.jsonl — заменена пустым файлом, цель цела (600, ROOT)", not os.path.islink(os.path.join(tg, "cards.jsonl"))
          and oct(os.lstat(vic).st_mode & 0o777) == "0o600" and open(vic).read() == "ROOT" and oct(os.lstat(os.path.join(tg, "cards.jsonl")).st_mode & 0o777) == "0o660")
    vic2 = os.path.join(T, "victim-hl"); open(vic2, "w").write("ROOT2"); os.chmod(vic2, 0o600); os.unlink(os.path.join(tg, "cards.jsonl")); os.link(vic2, os.path.join(tg, "cards.jsonl"))
    S.own_file(tg, "cards.jsonl", ME, ME, 0o660)
    check("own_file: жёсткая ссылка — отцеплена, права цели не тронуты", oct(os.lstat(vic2).st_mode & 0o777) == "0o600" and os.lstat(os.path.join(tg, "cards.jsonl")).st_nlink == 1)
    open(os.path.join(tg, "cards.jsonl"), "a").write("x\n"); S.own_file(tg, "cards.jsonl", ME, ME, 0o660)
    check("own_file: обычный файл — содержимое цело, права 660", open(os.path.join(tg, "cards.jsonl")).read() == "x\n")
    os.mkdir(os.path.join(tg, "dir.jsonl"))
    check("own_file: папка на месте файла — отказ", refuses(S.own_file, tg, "dir.jsonl", ME, ME, 0o660))
    base = tempfile.mkdtemp(dir=T); S.own(os.path.join(base, "keys"), ME, ME, 0o700)
    check("own: новая папка 700 своего uid", oct(os.lstat(os.path.join(base, "keys")).st_mode & 0o7777) == "0o700")
    os.symlink(tempfile.mkdtemp(dir=T), os.path.join(base, "io"))
    check("own: io — ссылка → отказ", refuses(S.own, os.path.join(base, "io"), ME, ME, 0o2750))
    S.own(os.path.join(base, "io2"), ME, ME, 0o2750)
    check("own: io 2750 с setgid", oct(os.lstat(os.path.join(base, "io2")).st_mode & 0o7777) == "0o2750")
    if os.geteuid() != 0: print("ℹ️  чужой uid и chown корня на root — под root (wall_probe), тут не root")
    check("persistent: та же папка, что «/» → не постоянный том", S.persistent("/", "/") is False)

    # CTO 10.11: four cases of what the volume held, through prepare() itself (not root here: owners are faked to no-ops)
    real_fchown = os.fchown
    if os.geteuid() != 0: os.fchown = lambda *a: None
    try:
        def prep(r, host=None):
            return S.prepare({"MILA_STATE": "data:" + r, "MILA_KIT": T}, ME, ME, ME)
        r = tempfile.mkdtemp(dir=T); L = prep(r)
        check("4 случая (1): пустой том — новая Мила, home/ с маркером, переносить нечего", L["moved"] == 0 and sorted(os.listdir(r)) == ["home", "io", "keys"]
              and os.path.isfile(os.path.join(r, "home", S.HOME_MARK)) and not L.get("claude_only"), (os.listdir(r), L))
        r = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(r, "work")); open(os.path.join(r, "work", "NOW.md"), "w").write("w")
        os.makedirs(os.path.join(r, ".claude", "projects", "-home-agent", "memory")); os.mkdir(os.path.join(r, "home"))
        L = prep(r)
        check("4 случая (2): старая Мила (work/) + пустой home/ от WORKDIR — переезд, память переименована", L["moved"] == 2 and L["projects_renamed"] == 1
              and open(os.path.join(r, "home", "work", "NOW.md")).read() == "w" and not os.path.exists(os.path.join(r, "work")), L)
        r = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(r, ".claude")); open(os.path.join(r, S.HOME_MARK), "w").close(); L = prep(r)
        check("4 случая (2б): старая Мила по маркеру .mila-home (без work/) — переезд", L["moved"] == 2 and os.path.isdir(os.path.join(r, "home", ".claude")), L)
        r = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(r, ".claude", "projects", "-root", "memory")); open(os.path.join(r, ".claude", "settings.json"), "w").write("{\"u\":1}")
        L = prep(r)
        check("4 случая (3): только Claude Code (.claude без work/ и маркера) — не тронут и не перенесён, Мила в home/", L["moved"] == 0 and L.get("claude_only") is True
              and open(os.path.join(r, ".claude", "settings.json")).read() == "{\"u\":1}" and os.listdir(os.path.join(r, ".claude", "projects")) == ["-root"]
              and os.path.isfile(os.path.join(r, "home", S.HOME_MARK)) and not os.path.exists(os.path.join(r, "home", ".claude")), (os.listdir(r), L))
        L2 = prep(r)
        check("4 случая (3): второй старт — так же ничего не переносит", L2["moved"] == 0 and os.path.isdir(os.path.join(r, ".claude")), L2)
        host = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(host, ".claude")); open(os.path.join(host, ".claude", "x"), "w").write("host")
        r = os.path.join(host, "vol"); os.mkdir(r); os.mkdir(os.path.join(r, "work")); prep(r)
        check("4 случая (4): ~/.claude хоста рядом с томом — не тронут", open(os.path.join(host, ".claude", "x")).read() == "host" and sorted(os.listdir(host)) == [".claude", "vol"])
    finally:
        os.fchown = real_fchown
    print("итог %d/%d" % (ok, n))
finally:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok == n else 1)
