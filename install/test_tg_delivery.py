#!/usr/bin/env python3
"""tg_delivery: строка в общий журнал доставки (формат плагина), HMAC с солью без id, HTTPError Telegram разобран, сеть — network,
шум не в счёте; heartbeat._tg_send пишет в журнал и не падает. python3 install/test_tg_delivery.py"""
import io, json, os, sys, tempfile, urllib.error
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); os.environ["TELEGRAM_STATE_DIR"] = T
sys.path.insert(0, H); import tg_delivery as D
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
GROUP = "-100" + "555000" + "999"; OWNER = "555000" + "777"
lines = lambda: [json.loads(l) for l in open(os.path.join(T, "delivery.jsonl"))]
r = D.call(lambda: {"ok": True, "result": {}}, "sendMessage", OWNER, via="heartbeat")
chk("ok → строка ok, via, без id", r[0] and lines()[-1]["ok"] and lines()[-1]["via"] == "heartbeat" and OWNER not in open(os.path.join(T, "delivery.jsonl")).read())
def http(code, desc):
    def do():
        raise urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(json.dumps({"ok": False, "error_code": code, "description": desc}).encode()))
    return do
r = D.call(http(400, "Bad Request: chat not found"), "sendMessage", GROUP)
chk("HTTPError 400 chat not found → no_chat, описание дословно, ok False без исключения", r[0] is False and lines()[-1]["cls"] == "no_chat" and lines()[-1]["desc"] == "Bad Request: chat not found", lines()[-1])
def boom(): raise OSError("net down")
r = D.call(boom, "sendMessage", GROUP)
chk("сеть → network", lines()[-1]["cls"] == "network" and r[0] is False)
D.call(http(400, "Bad Request: message is not modified"), "editMessageText", GROUP)
st = json.load(open(os.path.join(T, "delivery-status.json")))
chk("шум не считается сбоем; счёт по классам без чатов", st["ok"] == 1 and st["fail"].get("no_chat") == 1 and st["fail"].get("network") == 1 and "noise" not in st["fail"] and "555000" not in json.dumps(st), st)
chk("соль 600, журнал 600", oct(os.stat(os.path.join(T, "delivery.salt")).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.join(T, "delivery.jsonl")).st_mode & 0o777) == "0o600")
import hmac, hashlib
salt = open(os.path.join(T, "delivery.salt")).read().strip()
chk("HMAC тот же, что у плагина (sha256, соль из delivery.salt, 16 знаков)", lines()[1]["chat"] == hmac.new(salt.encode(), GROUP.encode(), hashlib.sha256).hexdigest()[:16])
# heartbeat
sys.path.insert(0, os.path.join(H, "..", "heartbeat")); import heartbeat as HB
import urllib.request
orig = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(b'{"ok":false,"error_code":403,"description":"Forbidden: bot was blocked by the user"}')))
res = HB._tg_send("1:" + "x" * 10, OWNER, "текст-сигнала")
urllib.request.urlopen = orig
chk("heartbeat._tg_send: 403 → False без исключения, строка blocked via heartbeat, текста нет", res is False and lines()[-1]["cls"] == "blocked" and lines()[-1]["via"] == "heartbeat" and "текст-сигнала" not in open(os.path.join(T, "delivery.jsonl")).read(), lines()[-1])
# bot_send
sys.path.insert(0, os.path.join(H, "..", "packs", "manager", "bot-send")); import bot_send as B
cls = [c for c in vars(B).values() if isinstance(c, type) and hasattr(c, "_api")][0]
o = cls.__new__(cls); o.token = "1:" + "x" * 10
urllib.request.urlopen = lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.HTTPError("u", 400, "x", {}, io.BytesIO(b'{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}')))
res = o._api("sendMessage", {"chat_id": GROUP, "text": "рассылка"})
urllib.request.urlopen = orig
chk("bot_send._api: сбой → ответ Telegram как был, строка no_chat via bot_send", res.get("description") == "Bad Request: chat not found" and lines()[-1]["via"] == "bot_send" and lines()[-1]["cls"] == "no_chat", lines()[-1])
n0 = len(lines()); o._api.__func__  # getMe не пишется
urllib.request.urlopen = lambda req, timeout=0: io.BytesIO(b'{"ok":true,"result":{}}')
o._api("getMe", {}); urllib.request.urlopen = orig
chk("bot_send: getMe в журнал не идёт", len(lines()) == n0)
import datetime as _dt
os.environ["TZ"] = "UTC"
D.record("sendMessage", OWNER, True, now=_dt.datetime(2026, 11, 4, 21, 30, tzinfo=_dt.timezone.utc))
chk("TZ=UTC задан, 21:30Z → день по TZ (04.11), как у плагина", json.load(open(os.path.join(T, "delivery-status.json")))["day"] == "2026-11-04")
del os.environ["TZ"]
D.record("sendMessage", OWNER, True, now=_dt.datetime(2026, 11, 4, 21, 30, tzinfo=_dt.timezone.utc))
chk("TZ не задан, 21:30Z → день по Ташкенту 05.11, как у плагина", json.load(open(os.path.join(T, "delivery-status.json")))["day"] == "2026-11-05")
import shutil; shutil.rmtree(T)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
