#!/usr/bin/env python3
"""io_perms.py (audit 09.11, №9): io/ loses every group/other write, the session's shared files get group rights,
no link and no hard link is followed. Usage: python3 test_io_perms.py"""
import os, shutil, stat, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import io_perms as P

ok = n = 0
def check(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:200]))
mode = lambda p: stat.S_IMODE(os.lstat(p).st_mode)

T = tempfile.mkdtemp(prefix="io-perms-")
try:
    tgd = os.path.join(T, "telegram"); iod = os.path.join(tgd, "io"); con = os.path.join(iod, "consent")
    os.makedirs(con); os.makedirs(os.path.join(tgd, "chats"))
    files = {os.path.join(con, "decisions.jsonl"): 0o660, os.path.join(con, "hmac.key"): 0o660, os.path.join(iod, "owners.json"): 0o664,
             os.path.join(iod, "taps.jsonl"): 0o640, os.path.join(tgd, "access.json"): 0o600, os.path.join(tgd, "chats", "a.json"): 0o600}
    for p, m in files.items(): open(p, "w").write("{}"); os.chmod(p, m)
    os.chmod(iod, 0o2770); os.chmod(con, 0o2770); os.chmod(os.path.join(tgd, "chats"), 0o700)   # what chmod -R g+rwX left behind
    outside = os.path.join(T, "system-file"); open(outside, "w").write("x"); os.chmod(outside, 0o600)
    os.link(outside, os.path.join(tgd, "hard.json"))
    odir = os.path.join(T, "elsewhere"); os.mkdir(odir, 0o700); open(os.path.join(odir, "f"), "w").write("x"); os.chmod(os.path.join(odir, "f"), 0o600)
    os.symlink(odir, os.path.join(tgd, "link-dir")); os.symlink(os.path.join(odir, "f"), os.path.join(tgd, "link-file"))
    os.symlink(outside, os.path.join(iod, "link-in-io"))

    P.share(tgd, iod, os.getuid()); taps_after_share = mode(os.path.join(iod, "taps.jsonl")); P.lock(iod)

    check("журнал согласий: запись группы снята (660 → 640)", mode(os.path.join(con, "decisions.jsonl")) == 0o640, oct(mode(os.path.join(con, "decisions.jsonl"))))
    check("ключ подписи согласий: запись группы снята", mode(os.path.join(con, "hmac.key")) == 0o640)
    check("список владельцев: запись группы и всех снята (664 → 640)", mode(os.path.join(iod, "owners.json")) == 0o640)
    check("папки io/ и consent/: 2770 → 2750, setgid цел", mode(iod) == 0o2750 and mode(con) == 0o2750, (oct(mode(iod)), oct(mode(con))))
    check("share в io/ не заходит (taps сразу после share — 640 как был)", taps_after_share == 0o640, oct(taps_after_share))
    check("общие файлы сессии — группе чтение/запись (600 → 660)", mode(os.path.join(tgd, "access.json")) == 0o660 and mode(os.path.join(tgd, "chats", "a.json")) == 0o660)
    check("папка сессии — группе rwx (700 → 770)", mode(os.path.join(tgd, "chats")) == 0o770)
    check("жёсткая ссылка на «системный» файл — его права не тронуты", mode(outside) == 0o600)
    check("ссылка на папку и файл вне — не идём, права целы", mode(odir) == 0o700 and mode(os.path.join(odir, "f")) == 0o600)
    check("повторный проход — ничего не открывает обратно", (P.share(tgd, iod, os.getuid()), P.lock(iod)) and mode(os.path.join(con, "decisions.jsonl")) == 0o640)
    r = subprocess.run([sys.executable, "-I", os.path.join(H, "io_perms.py"), tgd, iod, str(os.getuid())], capture_output=True, text=True)
    check("запуск из entrypoint — строка итога, код 0", r.returncode == 0 and r.stdout.startswith("io_perms: shared"), r.stdout + r.stderr)
    # control: what the old line did to the same tree
    os.chmod(os.path.join(con, "decisions.jsonl"), 0o640)
    subprocess.run(["chmod", "g+rwX", "-R", tgd], check=False)
    check("контроль: старый chmod -R g+rwX открывал журнал согласий группе", mode(os.path.join(con, "decisions.jsonl")) & 0o020 != 0)
    if os.geteuid() != 0: print("ℹ️  файлы чужого uid (share их не трогает) — проверяется под root, тут не root")
    print("итог %d/%d" % (ok, n))
finally:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok == n else 1)
