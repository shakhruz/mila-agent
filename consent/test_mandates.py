#!/usr/bin/env python3
"""Standing permissions (mandates): the session may only ask; the proxy draws the card with the exact terms; only the owner's
press opens it; within its targets, its days (≤7) and its day's count and money (≤$10) the action runs without a card and the
owner gets a receipt with «Stop»; outside them — the usual card; kinds without «mandate_ok» never get one.
Run: python3 test_mandates.py"""
import os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="mand-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import consent_proxy as cp, decisions as D
OWNER, OTHER = str(int("555" + "000111")), str(int("555" + "000222")); os.environ["MILA_OWNER_ID"] = OWNER
STATE = os.path.join(T, "state"); os.makedirs(os.path.join(T, "home"))
CFG = {"owner_id_env": "MILA_OWNER_ID", "home": os.path.join(T, "home"), "state_dir": STATE, "ttl_min": 15,
       "categories": {"spend_images": {"enabled": True, "title": "картинки", "exec": ["true"], "mandate_ok": True, "fields": ["text", "targets", "cost_usd"]},
                      "pack": {"enabled": True, "exec": ["true"]}}}
CARDS, RUNS, NOW = [], [], [1_800_000_000.0]
px = cp.Proxy(CFG, send=lambda text, kb: CARDS.append((text, kb)) or True, run=lambda cmd, body: RUNS.append(body) or {"ok": True}, now=lambda: NOW[0])
def btn(i=-1, k=0): return CARDS[i][1][0][k]["callback_data"]
check("полномочие на вид без mandate_ok (пак) — отказ", px.mandate_ask("pack", ["x"], 1, 1, 0)["status"] == "denied")
check("сверх потолка: 8 дней или $11 в день — отказ", px.mandate_ask("spend_images", ["gen"], 8, 5, 5)["status"] == "denied" and px.mandate_ask("spend_images", ["gen"], 3, 5, 11)["status"] == "denied")
check("без названных целей — отказ", px.mandate_ask("spend_images", [], 3, 5, 5)["status"] == "denied")
r = px.mandate_ask("spend_images", ["gen"], 3, 2, 1.0)
check("запрос полномочия — карточка владельцу с точными условиями", r["status"] == "asked" and "3 дн." in CARDS[-1][0] and "до $1 в день" in CARDS[-1][0] and "До 2 действий" in CARDS[-1][0], CARDS[-1][0])
P = {"text": "кот в шляпе", "targets": ["gen"], "cost_usd": 0.4}
check("до нажатия — обычная карточка, не исполнено", px.request("spend_images", P)["status"] == "asked" and not RUNS)
check("чужой нажал «Да» на полномочии — ignored, не открыто", px.callback(CARDS[0][1][0][0]["callback_data"], OTHER, OTHER)["status"] == "ignored")
check("владелец в личке нажал — granted", px.callback(CARDS[0][1][0][0]["callback_data"], OWNER, OWNER)["status"] == "granted")
nc = len(CARDS); r = px.request("spend_images", dict(P, text="собака"))
check("в пределах полномочия — исполнено без карточки, квитанция с «Стоп»", r["status"] == "done" and len(RUNS) == 1 and len(CARDS) == nc + 1 and "Сделано по полномочию" in CARDS[-1][0] and CARDS[-1][1][0][0]["callback_data"].endswith(".s"), r)
r = px.request("spend_images", dict(P, text="лиса", cost_usd=0.7))
check("сверх денег дня ($0.4 + $0.7 > $1) — обычная карточка", r["status"] == "asked" and len(RUNS) == 1, r)
r = px.request("spend_images", dict(P, text="ёж", targets=["other"]))
check("другая цель — обычная карточка", r["status"] == "asked" and len(RUNS) == 1, r)
px.request("spend_images", dict(P, text="сова", cost_usd=0.1)); r = px.request("spend_images", dict(P, text="уж", cost_usd=0.1))
check("сверх числа в день (2) — обычная карточка", r["status"] == "asked" and len(RUNS) == 2, r)
NOW[0] += 86400 + 1; r = px.request("spend_images", dict(P, text="на другой день"))
check("на другой день — снова по полномочию", r["status"] == "done" and len(RUNS) == 3, r)
stop = [c for c in CARDS if "Сделано по полномочию" in c[0]][-1][1][0][0]["callback_data"]
check("«Стоп» от чужого — ignored", px.callback(stop, OTHER, OTHER)["status"] == "ignored")
check("«Стоп» владельца — остановлено", px.callback(stop, OWNER, OWNER)["status"] == "stopped")
check("после «Стоп» — обычная карточка", px.request("spend_images", dict(P, text="после стопа"))["status"] == "asked" and len(RUNS) == 3)
r2 = px.mandate_ask("spend_images", ["gen"], 1, 5, 5); px.callback(btn(), OWNER, OWNER); NOW[0] += 86400 * 1 + 10
check("срок вышел — обычная карточка", px.request("spend_images", dict(P, text="после срока"))["status"] == "asked" and len(RUNS) == 3)
j = open(os.path.join(STATE, "decisions.jsonl")).read(); v = D.verify(os.path.join(STATE, "decisions.jsonl"))
check("в журнале решений: mandate_open, mandate_use, mandate_stop; цепочка цела", all('"ev": "%s"' % e in j for e in ("mandate_open", "mandate_use", "mandate_stop")) and v[0], v)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
