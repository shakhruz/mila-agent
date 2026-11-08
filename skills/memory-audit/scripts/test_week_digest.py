#!/usr/bin/env python3
"""week_digest.py: day pages (made by day_digest.py from live-format journals) → one week page: sums by type, each day linked,
a missing day said, ≤ 3 KB, the same file twice, a linked-in day page refused. Dates from today. Run: python3 test_week_digest.py"""
import atexit, datetime, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="dweek-"); atexit.register(shutil.rmtree, T, True)
W = os.path.join(T, "work"); os.makedirs(os.path.join(W, "memory"))
last = datetime.date.today() - datetime.timedelta(days=7); y, w, _ = last.isocalendar(); WK = "%d-W%02d" % (y, w)
mon = datetime.date.fromisocalendar(y, w, 1); days = [mon, mon + datetime.timedelta(days=2), mon + datetime.timedelta(days=4)]
with open(os.path.join(W, "dela.jsonl"), "w", encoding="utf-8") as f:
    for k, d in enumerate(days):
        for i in range(k + 2):
            f.write(json.dumps({"дата": d.isoformat(), "дело": "пакет d%d-%d" % (k, i), "тип": "код" if i % 2 else "план", "для": "команда",
                                "ступень": "сделала", "улика": "file:outbox/sent/x/NOTE.md", "результат": "доставлен"}, ensure_ascii=False) + "\n")
open(os.path.join(W, "NOW.md"), "w", encoding="utf-8").write("".join("- %02d.%02d 10:00: ход дня %d\n" % (d.day, d.month, k) for k, d in enumerate(days)))
for d in days:
    subprocess.run([sys.executable, os.path.join(H, "day_digest.py"), "--work", W, "--date", d.isoformat()], check=True, capture_output=True)
run = lambda *a: subprocess.run([sys.executable, os.path.join(H, "week_digest.py"), "--work", W] + list(a), capture_output=True, text=True)
r = run("--week", WK); P = os.path.join(W, "memory", "weeks", WK + ".md"); txt = open(P, encoding="utf-8").read() if os.path.exists(P) else ""
chk("страница недели записана", r.returncode == 0 and txt.startswith("# Неделя " + WK), (r.stdout, r.stderr))
chk("сумма дел за неделю: 2+3+4 = 9, по типам (план 5, код 4)", "— 9 дел" in txt and "план 5" in txt and "код 4" in txt, txt[:300])
chk("каждый день со страницей — ссылкой, без страницы — так и сказано (4 дня)", txt.count("](../days/") == 3 and txt.count("страницы дня нет") == 4, txt)
chk("ход недели — строки дней", all(("ход дня %d" % k) in txt for k in range(3)))
chk("не больше 3 КБ, права 600", len(txt.encode("utf-8")) <= 3072 and oct(os.stat(P).st_mode & 0o777) == "0o600")
run("--week", WK); chk("второй прогон — тот же файл", open(P, encoding="utf-8").read() == txt)
chk("страницы дней на месте", all(os.path.exists(os.path.join(W, "memory", "days", d.isoformat() + ".md")) for d in days))
# a day page that is a link (out of the home) is not read
miss = mon + datetime.timedelta(days=1); outside = os.path.join(T, "outside.md"); open(outside, "w").write("## Сделано — 999 дел: чужое 999\n")
os.symlink(outside, os.path.join(W, "memory", "days", miss.isoformat() + ".md"))
run("--week", WK); t2 = open(P, encoding="utf-8").read()
chk("страница дня — симлинк наружу: не читается", "999" not in t2 and "— 9 дел" in t2, t2[:300])
chk("неделя не по формату — отказ; несуществующая — отказ", run("--week", "2026-45").returncode != 0 and run("--week", "2026-W60").returncode != 0)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
