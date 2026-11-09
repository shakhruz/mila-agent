#!/usr/bin/env python3
"""The key store lives outside the session's home, and root's move of old keys follows no link (audit 09.11, №1).
Attacks from the session's side, as files it can plant in its home before a start: a hard link to a system file, a symlink
instead of a key file or a folder, a swapped store. Usage: python3 test_keyd_store.py"""
import os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import mila_keyd as K

ok = n = 0
def check(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:200]))

for _k, _var in K.ENV_KEYS: os.environ.pop(_var, None)   # only planted files count here, not this machine's variables
T = tempfile.mkdtemp(prefix="keyd-store-")
try:
    ANT = "sk-" + "ant-" + "oat01-" + "A" * 40; DG = "abcd1234" * 5; BOT = "77777" + ":" + "T" * 35
    def home():
        h = tempfile.mkdtemp(dir=T); os.makedirs(os.path.join(h, ".mila-auth")); os.makedirs(os.path.join(h, "work", "secrets")); return h
    def store():
        s = tempfile.mkdtemp(dir=T); K.KEYS = s; return s

    # 1. a hard link to a «system» file in place of an old key file: not read, not wiped
    hm, st = home(), store()
    victim = os.path.join(T, "shadow"); open(victim, "w").write("root:$6$hash:19000:0:99999:7:::\n")
    os.link(victim, os.path.join(hm, ".mila-auth", "bot_token"))
    K.migrate(hm)
    check("жёсткая ссылка на системный файл — не прочитана и не стёрта", open(victim).read().startswith("root:$6$") and os.listdir(st) == [])

    # 2. a symlink in place of the key file — even when it points at a key-shaped value
    hm, st = home(), store()
    v2 = os.path.join(T, "elsewhere-token"); open(v2, "w").write(ANT + "\n")
    os.symlink(v2, os.path.join(hm, ".mila-auth", "oauth_token"))
    K.migrate(hm)
    check("ссылка вместо файла ключа — не идём по ней, цель цела", open(v2).read().strip() == ANT and os.listdir(st) == [])

    # 3. a symlink in place of a folder on the way (work → elsewhere)
    hm, st = home(), store(); shutil.rmtree(os.path.join(hm, "work"))
    od = os.path.join(T, "other"); os.makedirs(os.path.join(od, "secrets")); open(os.path.join(od, "secrets", "deepgram.env"), "w").write("DEEPGRAM_API_KEY=%s\n" % DG)
    os.symlink(od, os.path.join(hm, "work"))
    K.migrate(hm)
    check("ссылка вместо папки по пути — не идём, чужой файл цел", os.path.exists(os.path.join(od, "secrets", "deepgram.env")) and os.listdir(st) == [])

    # 4. the old store in the home (earlier versions): moved out, wiped, folder gone
    hm, st = home(), store(); os.makedirs(os.path.join(hm, ".keys"))
    open(os.path.join(hm, ".keys", "deepgram"), "w").write(DG + "\n")
    moved = K.migrate(hm)
    check("старое хранилище в доме — ключ перенесён, файл стёрт, папки нет", moved == ["deepgram"] and open(os.path.join(st, "deepgram")).read().strip() == DG
          and not os.path.exists(os.path.join(hm, ".keys")), moved)

    # 5. a hard link inside the old store — skipped as well
    hm, st = home(), store(); os.makedirs(os.path.join(hm, ".keys"))
    v5 = os.path.join(T, "v5"); open(v5, "w").write(DG + "\n"); os.link(v5, os.path.join(hm, ".keys", "deepgram"))
    K.migrate(hm)
    check("жёсткая ссылка в старом хранилище — пропущена, цель цела", open(v5).read().strip() == DG and os.listdir(st) == [])

    # 6. a plain old key file still moves and is wiped (the normal path keeps working)
    hm, st = home(), store()
    open(os.path.join(hm, ".mila-auth", "oauth_token"), "w").write(ANT + "\n")
    check("обычный старый файл — перенесён и стёрт", K.migrate(hm) == ["anthropic"] and not os.path.exists(os.path.join(hm, ".mila-auth", "oauth_token")))

    # №10: one bad old file (a session's bytes) — that key is skipped, the rest still move, the start goes on
    hm, st = home(), store(); open(os.path.join(hm, ".mila-auth", "oauth_token"), "w").write(ANT + "\n")
    real_take = K.take_old
    def bad_take(h, rel, field, **kw):
        if rel.endswith("bot_token"): raise ValueError("bad bytes")
        return real_take(h, rel, field, **kw)
    K.take_old = bad_take
    try: moved = K.migrate(hm); r10 = True
    except Exception as e: moved, r10 = [], repr(e)
    K.take_old = real_take
    check("№10: сбой на одном старом файле — ключ пропущен, остальные перенесены, без исключения", r10 is True and moved == ["anthropic"], (r10, moved))

    # 7. a key in the store that is a symlink — the keeper does not follow it
    st = store(); v7 = os.path.join(T, "v7"); open(v7, "w").write(DG + "\n"); os.symlink(v7, os.path.join(st, "deepgram"))
    check("ключ-ссылка в хранилище — не читается", K.key("deepgram") == "")

    # 8. the store itself: a symlink stops the start; a fresh one is made 700
    sp = os.path.join(T, "s-link"); os.symlink(tempfile.mkdtemp(dir=T), sp)
    try: K.own_store(sp, os.getuid()); r8 = False
    except (OSError, SystemExit): r8 = True
    check("хранилище-ссылка — старт отказывает", r8)
    fresh = os.path.join(T, "var", "lib", "mila-keys"); os.close(K.own_store(fresh, os.getuid()))
    check("новое хранилище — папка 700", oct(os.lstat(fresh).st_mode & 0o777) == "0o700")
    if os.geteuid() == 0:
        foreign = os.path.join(T, "foreign"); os.mkdir(foreign); os.chown(foreign, 4242, 4242)
        try: K.own_store(foreign, 1002); r9 = False
        except SystemExit: r9 = True
        check("хранилище чужого uid — старт отказывает", r9)
    else:
        print("ℹ️  хранилище чужого uid — проверяется под root (wall_probe), тут не root")

    # 9. /status: the bot's id only from a token of the checked shape, only digits
    check("id бота из настоящей формы токена", K.bot_id(BOT) == "77777")
    for bad in ("abc:" + "T" * 35, "77777", "77777:short", "1234:" + "T" * 35, "77777:" + "T" * 35 + "\n../x", ""):
        check("id бота из %r — пусто" % bad[:20], K.bot_id(bad) == "")
    print("итог %d/%d" % (ok, n))
finally:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok == n else 1)
