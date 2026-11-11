#!/usr/bin/env python3
"""subscription.py --own: a machine that writes its own report for another machine leaves out the entries it only received as
reports ("report") — otherwise the reader shows one sign-in twice. No network: the sign-in reader is replaced inside the process.
Run: python3 skills/subscription/test_subscription_own.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subscription as S
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
asked = []
S.load_accounts = lambda: [{"name": "Main", "credentials": "~/nowhere.json"}, {"name": "Laptop", "report": "~/nowhere-report.json"}]
S.collect_account = lambda entry, cache, force=False: (asked.append(entry["name"]), {"name": entry["name"], "windows": []})[1]
S.load_cache = lambda: {}; S.save_cache = lambda cache: None; S.local_spend = lambda: {}
st = S.collect(own_only=True)
chk("--own: only this machine's sign-in is in the report", [a["name"] for a in st["accounts"]] == ["Main"], st["accounts"])
chk("…and the report from the other machine is not even read", asked == ["Main"], asked)
asked.clear(); st = S.collect()
chk("without --own both are there, as before", [a["name"] for a in st["accounts"]] == ["Main", "Laptop"], st["accounts"])
asked.clear(); st = S.collect(local_only=True, own_only=True)
chk("--local with --own: no sign-in is asked at all", asked == [] and st["accounts"] == [], (asked, st))
import subprocess
r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscription.py"), "--help"], capture_output=True, text=True)
chk("the flag is in the help", "--own" in r.stdout, r.stdout[-200:])
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
