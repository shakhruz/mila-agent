#!/usr/bin/env python3
"""dela.py: запись со всеми полями; без улики, с ПДн, с общим «делом» — отказ; итог накопительный по типам; файл 600. Фикстуры — выдуманные."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); env = {**os.environ, "MILA_WORK": T}
D = lambda *a: subprocess.run([sys.executable, "-I", os.path.join(H, "dela.py"), *a], capture_output=True, text=True, env=env)
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
r = D("add", "--delo", "КП кофейня 04.11", "--tip", "КП", "--dlya", "лид·12", "--ulika", "msg:abc:15", "--stupen", "сделала")
L = os.path.join(T, "dela.jsonl")
chk("запись: строка с полями, файл 600", r.returncode == 0 and json.loads(open(L).read().splitlines()[0])["дело"] == "КП кофейня 04.11" and oct(os.stat(L).st_mode & 0o777) == "0o600", r.stderr)
chk("без улики — отказ", D("add", "--delo", "КП 2 04.11", "--tip", "КП", "--stupen", "сделала").returncode != 0)
chk("улика текстом, а не указателем — отказ", D("add", "--delo", "КП 3 04.11", "--tip", "КП", "--ulika", "он сказал да", "--stupen", "приняли").returncode != 0)
chk("общее слово «КП» вместо имени дела — отказ", D("add", "--delo", "КП", "--tip", "КП", "--ulika", "msg:a:1", "--stupen", "сделала").returncode != 0)
PH = "+998 90 " + "123 45 67"
chk("телефон в «для» — отказ", D("add", "--delo", "КП 4 04.11", "--tip", "КП", "--dlya", "Иван " + PH, "--ulika", "msg:a:2", "--stupen", "сделала").returncode != 0)
chk("@ник в результате — отказ", D("add", "--delo", "КП кофейня 04.11", "--tip", "КП", "--ulika", "msg:a:3", "--stupen", "результат", "--rezultat", "написал @ivan_k").returncode != 0)
chk("«для» = имя человека — отказ", D("add", "--delo", "КП 6 04.11", "--tip", "КП", "--dlya", "Иван Петров", "--ulika", "msg:a:5", "--stupen", "сделала").returncode != 0)
chk("«для» = «иван петров» строчными — отказ", D("add", "--delo", "КП 6b 04.11", "--tip", "КП", "--dlya", "иван петров", "--ulika", "msg:a:7", "--stupen", "сделала").returncode != 0)
chk("«для» = тип строчными — ок", D("add", "--delo", "КП 7 04.11", "--tip", "КП", "--dlya", "турфирма", "--ulika", "msg:a:6", "--stupen", "сделала").returncode == 0)
chk("улика file: несуществующий файл — отказ", D("add", "--delo", "КП 8 04.11", "--tip", "КП", "--ulika", "file:нет/такого.md", "--stupen", "сделала").returncode != 0)
open(os.path.join(T, "kp8.md"), "w").write("x")
chk("улика file: файл внутри work — ок; вне work — отказ", D("add", "--delo", "КП 8 04.11", "--tip", "КП", "--ulika", "file:kp8.md", "--stupen", "сделала").returncode == 0 and D("add", "--delo", "КП 9 04.11", "--tip", "КП", "--ulika", "file:/etc/hostname", "--stupen", "сделала").returncode != 0)
chk("улика commit: не хэш — отказ; msg без номера — отказ", D("add", "--delo", "КП 10 04.11", "--tip", "КП", "--ulika", "commit:сделала", "--stupen", "сделала").returncode != 0 and D("add", "--delo", "КП 10 04.11", "--tip", "КП", "--ulika", "msg:abc", "--stupen", "сделала").returncode != 0)
chk("то же дело и ступень дважды — «уже записано»", D("add", "--delo", "КП кофейня 04.11", "--tip", "КП", "--dlya", "лид·12", "--ulika", "msg:abc:15", "--stupen", "сделала").returncode != 0)
chk("ступень не из трёх — отказ", D("add", "--delo", "КП 5 04.11", "--tip", "КП", "--ulika", "msg:a:4", "--stupen", "почти").returncode != 0)
D("add", "--delo", "КП кофейня 04.11", "--tip", "КП", "--ulika", "msg:abc:16", "--stupen", "приняли")
D("add", "--delo", "Пост канал 04.11", "--tip", "пост", "--ulika", "link:https://t.me/c/1/2", "--stupen", "результат", "--rezultat", "12 реакций")
it = json.loads(D("itog", "--json").stdout)
chk("итог накопительный: КП 3/1/0, пост 1/1/1", it["КП"] == {"сделала": 3, "приняли": 1, "результат": 0} and it["пост"] == {"сделала": 1, "приняли": 1, "результат": 1}, it)
chk("итог — только числа, без «для» и улик", "лид·12" not in D("itog").stdout and "msg:" not in D("itog").stdout)
import fcntl, time
hold = open(L, "a"); fcntl.flock(hold, fcntl.LOCK_EX)   # the journal is busy: both writers start and wait; old code had already read «no such line» by then
ps = [subprocess.Popen([sys.executable, "-I", os.path.join(H, "dela.py"), "add", "--delo", "КП разом 04.11", "--tip", "КП", "--ulika", "msg:r:1", "--stupen", "сделала"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env) for _ in range(2)]
time.sleep(1.5); busy = [p.poll() for p in ps]; fcntl.flock(hold, fcntl.LOCK_UN); hold.close()
rcs = [p.wait(timeout=30) for p in ps]
got = [l for l in open(L, encoding="utf-8").read().splitlines() if json.loads(l)["дело"] == "КП разом 04.11"]
chk("журнал занят — оба писателя ждут; после — одна строка, второму «уже записано»", busy == [None, None] and len(got) == 1 and sorted(rcs) == [0, 1], (busy, len(got), rcs))
import shutil; shutil.rmtree(T)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
