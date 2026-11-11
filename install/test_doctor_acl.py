#!/usr/bin/env python3
"""doctor and a journal that a server gives to named readers through an access list (ACL): group bits on such a file are the
list's mask, not the group's rights. Named read-only readers → a yellow line with their names, not red. A list that lets anyone
write, rights of the owning group, any «other» bit, no getfacl — red, as before. The allowance is for the journal only: the token
file and the access list stay strict. getfacl is replaced inside the process. Run: python3 install/test_doctor_acl.py"""
import importlib.util, os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="acl-"); ST = os.path.join(T, "state"); INB = os.path.join(ST, "inbound")
os.makedirs(INB, mode=0o700); os.chmod(ST, 0o700)
os.environ["TELEGRAM_" + "STATE_DIR"] = ST; os.environ["MILA_LANG"] = "ru"
spec = importlib.util.spec_from_file_location("doc", os.path.join(H, "doctor.py")); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
EV = D.EVENTS; TOKEN_FILE = D.ENV_FILE
open(EV, "w").write("{}\n"); open(TOKEN_FILE, "w").write("X=1\n")
class P:
    def __init__(s, rc, out): s.returncode, s.stdout, s.stderr = rc, out, ""
asked = []
def acl(text, rc=0):
    def run(cmd, **kw):
        if cmd and cmd[0] == "getfacl": asked.append(cmd[-1]); return P(rc, text)
        raise AssertionError(cmd)
    return run
def no_getfacl(cmd, **kw): raise FileNotFoundError("getfacl")
class R:
    def __init__(s): s.rows = []
    def add(s, *a): s.rows.append(a)
def perms(mode_ev=0o660, mode_tok=0o600):
    os.chmod(EV, mode_ev); os.chmod(TOKEN_FILE, mode_tok); asked.clear(); r = R(); D.check_perms(r)
    ev = [x for x in r.rows if "events.jsonl" in str(x[2])]; tok = [x for x in r.rows if os.path.basename(TOKEN_FILE) in str(x[2])]
    return ev[0] if ev else None, tok[0] if tok else None, r.rows
READ = "user::rw-\nuser:mila:r--\ngroup::---\nmask::rw-\nother::---\n"
real = D.subprocess.run
try:
    D.subprocess.run = acl(READ); ev, tok, rows = perms()
    chk("журнал 660 при списке «mila читает»: жёлтая строка с именем читателя, не красная", ev and ev[0] == D.WARN and "mila" in ev[2] and "ACL" in ev[2] and "660" in ev[2], ev)
    chk("…в подсказке — «убедитесь, что каждое имя — ваше»", ev and "каждое имя" in ev[3], ev)
    D.subprocess.run = acl(READ.replace("user:mila:r--", "user:mila:r--\ngroup:watch:r--")); ev, tok, rows = perms()
    chk("два читателя (пользователь и группа) — оба названы", ev and ev[0] == D.WARN and "mila" in ev[2] and "group watch" in ev[2], ev)
    D.subprocess.run = acl(READ.replace("user:mila:r--", "user:mila:rw-")); ev, tok, rows = perms()
    chk("в списке кто-то может ПИСАТЬ — красное, как раньше", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl(READ.replace("group::---", "group::r--")); ev, tok, rows = perms()
    chk("права у самой группы-владельца — красное", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl("user::rw-\ngroup::rw-\nother::---\n"); ev, tok, rows = perms()
    chk("списка нет, просто 660 — красное", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl(READ); ev, tok, rows = perms(mode_ev=0o664)
    chk("есть бит «остальным» (664) — красное, список даже не спрашиваю", ev and ev[0] == D.BAD and not asked, (ev, asked))
    D.subprocess.run = no_getfacl; ev, tok, rows = perms()
    chk("getfacl на машине нет — красное, как раньше, без падения", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl("", rc=1); ev, tok, rows = perms()
    chk("getfacl ответил ошибкой — красное", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl("что-то непонятное\n"); ev, tok, rows = perms()
    chk("вывод getfacl не разобрать — красное", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl("user::rw-\ngroup::---\nmask::rw-\nother::---\n"); ev, tok, rows = perms()
    chk("список есть, но названных читателей в нём нет — красное (660 ничем не объяснено)", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl(READ + "строка, которую не разобрать\n"); ev, tok, rows = perms()
    chk("среди понятных строк одна непонятная — красное: не знаю, что она разрешает", ev and ev[0] == D.BAD, ev)
    D.subprocess.run = acl(READ); ev, tok, rows = perms(mode_ev=0o600)
    chk("журнал 600 — зелёное, список не спрашиваю", ev and ev[0] == D.OK and not asked, (ev, asked))
    D.subprocess.run = acl(READ); ev, tok, rows = perms(mode_ev=0o600, mode_tok=0o660)
    chk("файл с ключом бота 660 при таком же списке — красное: послабление только для журнала", tok and tok[0] == D.BAD and not asked, (tok, asked))
finally:
    D.subprocess.run = real; shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
