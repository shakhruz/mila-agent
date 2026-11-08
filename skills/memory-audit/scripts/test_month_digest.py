#!/usr/bin/env python3
"""month_digest.py: week pages (made by week_digest.py from day pages) → one month page: sums, each week linked, a missing week
said, ≤ 3 KB, same file twice, a linked-in week page refused. Dates from today. Run: python3 test_month_digest.py"""
import atexit, datetime, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="dmon-"); atexit.register(shutil.rmtree, T, True)
W = os.path.join(T, "work"); os.makedirs(os.path.join(W, "memory"))
first = datetime.date.today().replace(day=1); last_m = first - datetime.timedelta(days=1); M = last_m.strftime("%Y-%m")
d1, d2 = last_m.replace(day=3), last_m.replace(day=17)
with open(os.path.join(W, "dela.jsonl"), "w", encoding="utf-8") as f:
    for d, k in ((d1, 3), (d2, 4)):
        for i in range(k):
            f.write(json.dumps({"дата": d.isoformat(), "дело": "пакет %s-%d" % (d.day, i), "тип": "код" if i % 2 else "план", "для": "команда",
                                "ступень": "сделала", "улика": "file:outbox/sent/x/NOTE.md", "результат": "доставлен"}, ensure_ascii=False) + "\n")
open(os.path.join(W, "NOW.md"), "w").write("")
for d in (d1, d2):
    subprocess.run([sys.executable, os.path.join(H, "day_digest.py"), "--work", W, "--date", d.isoformat()], check=True, capture_output=True)
    y, w, _ = d.isocalendar()
    subprocess.run([sys.executable, os.path.join(H, "week_digest.py"), "--work", W, "--week", "%d-W%02d" % (y, w)], check=True, capture_output=True)
run = lambda *a: subprocess.run([sys.executable, os.path.join(H, "month_digest.py"), "--work", W] + list(a), capture_output=True, text=True)
r = run("--month", M); P = os.path.join(W, "memory", "months", M + ".md"); txt = open(P, encoding="utf-8").read() if os.path.exists(P) else ""
chk("страница месяца записана", r.returncode == 0 and txt.startswith("# Месяц " + M), (r.stdout, r.stderr))
chk("сумма за месяц: 3+4 = 7 (план 4, код 3)", "— 7 дел" in txt and "план 4" in txt and "код 3" in txt, txt[:300])
chk("две недели — ссылками, остальные — «страницы недели нет»", txt.count("](../weeks/") == 2 and "страницы недели нет" in txt, txt)
chk("≤ 3 КБ, 600", len(txt.encode("utf-8")) <= 3072 and oct(os.stat(P).st_mode & 0o777) == "0o600")
run("--month", M); chk("второй прогон — тот же файл", open(P, encoding="utf-8").read() == txt)
wk = sorted(x for x in os.listdir(os.path.join(W, "memory", "weeks")))[0]; wp = os.path.join(W, "memory", "weeks", wk)
outside = os.path.join(T, "out.md"); open(outside, "w").write("## Сделано — 999 дел: чужое 999\n"); os.unlink(wp); os.symlink(outside, wp)
run("--month", M); chk("страница недели — симлинк наружу: не читается", "999" not in open(P, encoding="utf-8").read())
chk("месяц не по формату — отказ", run("--month", "2026-13").returncode != 0 and run("--month", "11.2026").returncode != 0)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
