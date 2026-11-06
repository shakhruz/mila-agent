#!/usr/bin/env python3
"""Mila Agent is decided by the machine (the receiver's OS user exists), not by MILA_CONSENT_SOCKET: with the variable unset —
or pointing at another socket — packs, updates, paid generations and bot-send still go only through the image's proxy socket,
and with no proxy there they are refused, never the old --yes / --card path. Run: python3 test_agent_mode.py"""
import argparse, os, pwd, sys, tempfile, types
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(H, "..", "..")); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="am-"); os.environ.update(HOME=T, CLAUDE_CONFIG_DIR=os.path.join(T, ".claude"), MILA_WORK=os.path.join(T, "work"), MILA_KIT=REPO)
os.environ.pop("MILA_CONSENT_SOCKET", None)
sys.path.insert(0, H); import update as UP
sys.path.insert(0, os.path.join(REPO, "packs", "kartinki", "spend")); import spend as SP
sys.path.insert(0, os.path.join(REPO, "packs", "manager", "bot-send")); import request_send as RS
real = pwd.getpwnam
def agent(on):
    UP.io_uid = (lambda: 1003) if on else (lambda: None); SP.io_uid = UP.io_uid
    def fake(name):
        if name != "mila-io": return real(name)
        if on: return types.SimpleNamespace(pw_uid=1003)
        raise KeyError(name)
    pwd.getpwnam = fake
agent(True)
check("контейнер (есть mila-io), переменной нет — сокет посредника всё равно образа", UP.consent_sock() == SP.consent_sock() == RS.consent_sock() == "/run/mila-io/consent.sock")
os.environ["MILA_CONSENT_SOCKET"] = os.path.join(T, "fake.sock")
check("…переменная на другой сокет — не уводит (в контейнере только сокет образа)", UP.consent_sock() == "/run/mila-io/consent.sock" and RS.consent_sock() == "/run/mila-io/consent.sock")
os.environ.pop("MILA_CONSENT_SOCKET")
a = argparse.Namespace(card=None, yes="хозяин сказал да", sender="x")
try:
    UP.consent(a, "#pack-demo-1"); got = "прошло"
except SystemExit as e:
    got = str(e)
check("пак в контейнере без посредника: --yes строкой не проходит — отказ «посредник»", "посредник" in got, got)
agent(False)
check("обычная машина без переменной — посредника нет (старый путь только там)", UP.consent_sock() == "" and SP.consent_sock() == "" and RS.consent_sock() == "")
os.environ["MILA_CONSENT_SOCKET"] = "/tmp/x.sock"; check("обычная машина с переменной — посредник включён", UP.consent_sock() == "/tmp/x.sock")
pwd.getpwnam = real; print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
