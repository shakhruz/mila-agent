#!/usr/bin/env python3
"""Consent-only kinds (a pack install, an update): the proxy shows the card and records «confirmed» with the exact action's hash;
the tool runs the action itself after confirmed() finds that line — the chain intact, after the tool asked, not used before.
Run: python3 test_confirm.py"""
import json, os, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = os.path.realpath(tempfile.mkdtemp(prefix="conf-")); ok = n = 0   # macOS: /var is a link to /private/var — the proxy refuses attachments through a link
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import consent_proxy as cp
OWNER = str(int("555" + "000111")); os.environ["MILA_OWNER_ID"] = OWNER
HOME = os.path.join(T, "home"); os.makedirs(os.path.join(HOME, "work")); ST = os.path.join(T, "s"); DJ = os.path.join(ST, "decisions.jsonl")
CFG = {"owner_id_env": "MILA_OWNER_ID", "home": HOME, "state_dir": ST, "categories": {"pack": {"enabled": True, "title": "пак", "fields": ["text", "attachments"]}}}
CARDS, NOW = [], [1_800_000_000.0]
px = cp.Proxy(CFG, send=lambda t, kb: CARDS.append((t, kb)) or True, run=lambda *a: (_ for _ in ()).throw(AssertionError("no exec")), now=lambda: NOW[0])
arc = os.path.join(HOME, "work", "manager.zip"); open(arc, "wb").write(b"pack bytes")
P = {"text": "Поставить пак «Менеджер»", "attachments": [arc]}
t0 = NOW[0]; px.request("pack", P); px.callback(CARDS[-1][1][0][0]["callback_data"], OWNER, OWNER)
r = px.request("pack", P)
check("пак: «да» владельца → done, исполнителя посредник не зовёт, «confirmed»", r["status"] == "done" and r["result"].get("confirmed"), r)
import hashlib
h = cp.action_hash("pack", {"text": P["text"]}, [("manager.zip", hashlib.sha256(b"pack bytes").hexdigest())])
cid = cp.confirmed(DJ, "pack", h, t0)
check("инструмент находит «confirmed» ровно для этого пака (тот же хеш)", cid == r["result"]["confirmed"], cid)
h2 = cp.action_hash("pack", {"text": P["text"]}, [("manager.zip", hashlib.sha256(b"other bytes").hexdigest())])
check("другой архив (другой хеш) — не найдено", cp.confirmed(DJ, "pack", h2, t0) == "")
check("уже использованный id — не найдено второй раз", cp.confirmed(DJ, "pack", h, t0, used={cid}) == "")
check("подтверждение раньше, чем инструмент спросил, — не годится", cp.confirmed(DJ, "pack", h, NOW[0] + 1) == "")
L = open(DJ).read().splitlines(); x = json.loads(L[0]); x["ev"] = "x"; open(DJ, "w").write("\n".join([json.dumps(x)] + L[1:]) + "\n")
check("цепочка журнала нарушена — не найдено", cp.confirmed(DJ, "pack", h, t0) == "")
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
