#!/usr/bin/env python3
"""The notification gate: urgent goes at once — even at night — but only a lost login or a security event; everything else waits
for the summary (09:00 and 19:00 in the owner's zone), one message; the same thing once a day. Run: python3 test_notify.py"""
import datetime, os, shutil, sys, tempfile
from zoneinfo import ZoneInfo
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="ntf-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import consent_proxy as cp
os.environ["MILA_OWNER_ID"] = str(int("555" + "000111"))
TZ = ZoneInfo("Asia/Tashkent"); at = lambda h, m=0, d=6: datetime.datetime(2026, 11, d, h, m, tzinfo=TZ).timestamp()
SENT, NOW = [], [at(3)]
px = cp.Proxy({"owner_id_env": "MILA_OWNER_ID", "home": T, "state_dir": os.path.join(T, "s"), "tz": "Asia/Tashkent", "quiet": [22, 8], "categories": {}},
              send=lambda t, kb: SENT.append(t) or True, now=lambda: NOW[0])
r = px.notify("urgent", "login_lost", "Вход в Claude потерян — нужна новая ссылка")
check("03:00, потеря входа — сразу, хоть и ночь", r["status"] == "sent" and SENT and "Вход в Claude" in SENT[-1], r)
r = px.notify("urgent", "disk_full", "Диск заполнен на 91%")
check("«срочно» не из списка (диск) — не будит, ждёт сводки", r["status"] == "queued" and len(SENT) == 1, r)
check("то же самое второй раз за сутки — отброшено", px.notify("urgent", "login_lost", "Вход в Claude потерян — нужна новая ссылка")["status"] == "dropped")
px.notify("info", "spend", "Сегодня потрачено $1,20"); NOW[0] = at(8, 30)
check("08:30 — не час сводки, ничего не шлётся", px.summary() == 0 and len(SENT) == 1)
NOW[0] = at(9, 5)
check("09:05 — одна сводка со всем, что ждало", px.summary() == 2 and len(SENT) == 2 and "Диск" in SENT[-1] and "$1,20" in SENT[-1], SENT[-1:])
check("второй раз в тот же час — ничего", px.summary() == 0 and len(SENT) == 2)
for i in range(7): px.notify("urgent", "security", "чужое нажатие %d" % i)
check("срочных не больше 5 в сутки (вход + 4 сигнала безопасности, остальные в сводку)", len(SENT) == 2 + 4 and px._load("notify.json", {})["queue"], len(SENT))
check("невидимые знаки из текста уведомления убраны", px.notify("info", "x", "a\u202eb")["status"] == "queued" and "\u202e" not in str(px._load("notify.json", {})["queue"]))
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
