#!/usr/bin/env python3
"""decisions.jsonl: a hash chain — a changed, inserted or removed line breaks it; a cut tail is seen against the anchor.
Run: python3 test_decisions.py"""
import json, os, subprocess, sys, tempfile, shutil, threading
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H); import decisions as D
ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="dec-"); P = os.path.join(T, "decisions.jsonl")
for ev in ("asked", "granted", "executed"): D.append(P, {"event": ev, "id": "c1", "kind": "post", "hash": "ab" * 8})
r = D.verify(P)
check("три решения — цепочка цела, n=3", r[0] and r[1] == 3, r)
check("файл 0640", oct(os.stat(P).st_mode & 0o777) == "0o640")
anchor = subprocess.run([sys.executable, os.path.join(H, "decisions.py"), "head", P], capture_output=True, text=True).stdout.strip()
check("head даёт якорь n:h12", anchor.startswith("3:") and len(anchor) == 14, anchor)
L = open(P).read().splitlines()
def write(lines): open(P, "w").write("\n".join(lines) + "\n")
x = json.loads(L[1]); x["event"] = "declined"; write([L[0], json.dumps(x), L[2]])
check("строку поменяли задним числом («granted» → «declined») — ловится", not D.verify(P)[0] and "line 2" in D.verify(P)[3], D.verify(P))
write([L[0], L[2]]); check("строку удалили — ловится", not D.verify(P)[0], D.verify(P))
fake = dict(json.loads(L[0]), event="owner_word"); write([L[0], json.dumps(fake), L[1], L[2]]); check("строку вставили — ловится", not D.verify(P)[0])
write(L[:2]); r = D.verify(P)
check("хвост отрезали: без якоря цепочка цела (так и есть) …", r[0] and r[1] == 2, r)
r = D.verify(P, anchor); check("… с якорем из сводки — ловится", not r[0] and "tail was cut" in r[3], r)
write(L); D.append(P, {"event": "expired", "id": "c2"}); r = D.verify(P, anchor)
check("дописали после якоря — с якорем цело", r[0] and r[1] == 4, r)
rc = subprocess.run([sys.executable, os.path.join(H, "decisions.py"), "verify", P, "--anchor", "3:" + "0" * 12], capture_output=True, text=True)
check("verify с чужим якорем — код 1, «rewritten»", rc.returncode == 1 and "rewritten" in rc.stdout, rc.stdout)
P2 = os.path.join(T, "par.jsonl"); ts = [threading.Thread(target=lambda: [D.append(P2, {"event": "asked"}) for _ in range(20)]) for _ in range(5)]
[t.start() for t in ts]; [t.join() for t in ts]; r = D.verify(P2)
check("100 записей из 5 потоков — цепочка цела (запись под замком)", r[0] and r[1] == 100, r)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
