#!/usr/bin/env python3
"""The owner's night: a card asked in quiet hours waits for the morning (its 15 minutes count from then); a file changed
overnight — the card expires instead; more than 10 cards an hour — refused. Run: python3 test_night.py"""
import datetime, os, shutil, sys, tempfile
from zoneinfo import ZoneInfo
H = os.path.dirname(os.path.abspath(__file__)); T = os.path.realpath(tempfile.mkdtemp(prefix="night-")); ok = n = 0   # macOS: /var is a link to /private/var — the proxy refuses attachments through a link
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import consent_proxy as cp
OWNER = str(int("555" + "000111")); os.environ["MILA_OWNER_ID"] = OWNER
HOME = os.path.join(T, "home"); os.makedirs(os.path.join(HOME, "work"))
CFG = {"owner_id_env": "MILA_OWNER_ID", "home": HOME, "state_dir": os.path.join(T, "s"), "ttl_min": 15, "tz": "Asia/Tashkent", "quiet": [22, 8],
       "categories": {"publish_zernio": {"enabled": True, "title": "пост", "exec": ["true"]}}}
TZ = ZoneInfo("Asia/Tashkent"); at = lambda h, m=0: datetime.datetime(2026, 11, 5, h, m, tzinfo=TZ).timestamp()
CARDS, RUNS, NOW = [], [], [at(23)]
px = cp.Proxy(CFG, send=lambda t, kb: CARDS.append((t, kb)) or True, run=lambda c, b: RUNS.append(b) or {"ok": True}, now=lambda: NOW[0])
P = {"text": "ночной пост", "targets": ["a"]}
r = px.request("publish_zernio", P)
check("23:00 по поясу владельца — карточка не уходит, «deferred»", r["status"] == "deferred" and not CARDS, r)
check("повтор ночью — «deferred», не вторая", px.request("publish_zernio", P)["status"] == "deferred" and not CARDS)
NOW[0] = at(23, 50) + 3600 * 2; check("ночью flush ничего не шлёт", px.flush() == 0 and not CARDS)
att = os.path.join(HOME, "work", "pic.png"); open(att, "wb").write(b"one")
NOW[0] = at(23, 30); px.request("publish_zernio", {"text": "с файлом", "targets": ["a"], "attachments": [att]}); open(att, "wb").write(b"two")
NOW[0] = at(9) + 86400
check("утром flush шлёт отложенные; изменённый за ночь файл — не шлёт", px.flush() == 1 and len(CARDS) == 1 and "ночной пост" in CARDS[0][0], CARDS)
NOW[0] += 10 * 60
check("15 минут считаются с утра: нажатие через 10 мин после отправки — granted", px.callback(CARDS[0][1][0][0]["callback_data"], OWNER, OWNER)["status"] == "granted")
check("…и действие исполняется", px.request("publish_zernio", P)["status"] == "done" and len(RUNS) == 1)
j = open(os.path.join(CFG["state_dir"], "decisions.jsonl")).read()
check("в журнале: deferred, утреннее asked, expired «changed overnight»", '"ev": "deferred"' in j and '"after_night": true' in j and "changed overnight" in j)
NOW[0] = at(12) + 86400; rs = [px.request("publish_zernio", {"text": "днём %d" % i, "targets": ["a"]})["status"] for i in range(11)]
check("днём больше 10 карточек за час — 11-я отказ", rs[:10] == ["asked"] * 10 and rs[10] == "denied", rs)
px2 = cp.Proxy(dict(CFG, tz=None, state_dir=os.path.join(T, "s2")), send=lambda t, kb: CARDS.append((t, kb)) or True, run=lambda *a: {"ok": True}, now=lambda: at(23))
check("без часового пояса тихих часов нет — карточка сразу", px2.request("publish_zernio", P)["status"] == "asked")
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
