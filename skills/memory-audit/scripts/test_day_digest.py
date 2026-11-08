#!/usr/bin/env python3
"""day_digest.py: the day from this Mila's own journals (deeds, NOW lines, memory files), ≤ 2 KB, the same file on a second
run, nothing from chats, nothing deleted. Fixtures: the live line formats, dates from today. Run: python3 test_day_digest.py"""
import atexit, datetime, json, os, shutil, subprocess, sys, tempfile, time
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="dday-"); atexit.register(shutil.rmtree, T, True)
W = os.path.join(T, "work"); os.makedirs(os.path.join(W, "memory"))
day = (datetime.date.today() - datetime.timedelta(days=1)); D = day.isoformat(); other = (day - datetime.timedelta(days=1)).isoformat()
# dela.jsonl: the live row (snapshot of a real line's keys and values' shape)
row = lambda delo, tip, st, d=D: {"дата": d, "дело": delo, "тип": tip, "для": "команда", "ступень": st, "улика": "file:outbox/sent/%s/NOTE.md" % delo, "результат": "доставлен"}
with open(os.path.join(W, "dela.jsonl"), "w", encoding="utf-8") as f:
    for i in range(15): f.write(json.dumps(row("пакет p%02d" % i, "код" if i % 2 else "план", "сделала"), ensure_ascii=False) + "\n")
    f.write(json.dumps(row("пакет вчерашний", "код", "сделала", other), ensure_ascii=False) + "\n")
    f.write("{broken\n")
# NOW.md: the live line shape «- DD.MM HH:MM: …» and «- DD.MM тик: …»
dm = "%02d.%02d" % (day.day, day.month); dm0 = "%02d.%02d" % ((day - datetime.timedelta(days=1)).day, (day - datetime.timedelta(days=1)).month)
open(os.path.join(W, "NOW.md"), "w", encoding="utf-8").write("# Хозяин · где мы сейчас\n\n> шапка\n- %s 10:05: шаг один\n- %s тик: шаг два\n- %s 09:00: чужой день\nКлиент написал: «секретный текст»\n" % (dm, dm, dm0))
# memory: one file changed that day, one another day, the index and a digest never count
for name, d in (("lesson.md", day), ("old.md", day - datetime.timedelta(days=5)), ("MEMORY.md", day)):
    p = os.path.join(W, "memory", name); open(p, "w").write("x"); t = time.mktime(datetime.datetime.combine(d, datetime.time(12)).timetuple()); os.utime(p, (t, t))
run = lambda *a: subprocess.run([sys.executable, os.path.join(H, "day_digest.py"), "--work", W] + list(a), capture_output=True, text=True)
r = run("--date", D); P = os.path.join(W, "memory", "days", D + ".md")
txt = open(P, encoding="utf-8").read() if os.path.exists(P) else ""
chk("файл дня записан", r.returncode == 0 and txt.startswith("# День " + D), (r.stdout, r.stderr))
chk("дела дня: 15, по типам (код 7, план 8), чужой день и битая строка не считаются", "15 дел" in txt and "код 7" in txt and "план 8" in txt and "вчерашний" not in txt, txt[:400])
chk("12 дел строками и «ещё 3»", txt.count("· сделала ·") == 12 and "ещё 3" in txt, txt)
chk("ход дня — только строки этого дня из NOW.md", "шаг один" in txt and "шаг два" in txt and "чужой день" not in txt)
chk("из чатов ничего: строки NOW не этого вида не копируются", "секретный" not in txt and "Хозяин" not in txt)
chk("узнала: файл памяти этого дня, без индекса и без старого", "lesson.md" in txt and "old.md" not in txt and "MEMORY.md" not in txt)
chk("не больше 2 КБ", len(txt.encode("utf-8")) <= 2048, len(txt.encode("utf-8")))
chk("права 600, папка 700", oct(os.stat(P).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(P)).st_mode & 0o777) == "0o700")
r2 = run("--date", D); chk("второй прогон — тот же файл", open(P, encoding="utf-8").read() == txt)
chk("ничего не удалено: журналы на месте", all(os.path.exists(os.path.join(W, x)) for x in ("dela.jsonl", "NOW.md", "memory/lesson.md", "memory/old.md")))
# a big day: the ceiling cuts whole lines and says so
with open(os.path.join(W, "dela.jsonl"), "a", encoding="utf-8") as f:
    for i in range(40): f.write(json.dumps(row("очень длинное имя дела номер %02d " % i + "x" * 50, "код", "результат"), ensure_ascii=False) + "\n")
with open(os.path.join(W, "NOW.md"), "a", encoding="utf-8") as f:
    for i in range(20): f.write("- %s 11:%02d: длинная строка хода %s\n" % (dm, i, "y" * 120))
for i in range(15): open(os.path.join(W, "memory", "m%02d-%s.md" % (i, "z" * 60)), "w").write("x")
run("--date", D); big = open(P, encoding="utf-8").read()
chk("большой день: ≤ 2 КБ, обрезано целыми строками, с пометкой", len(big.encode("utf-8")) <= 2048 and "потолок 2 КБ" in big and big.endswith("\n"), len(big.encode("utf-8")))
chk("пустой дом — файл дня без падения", subprocess.run([sys.executable, os.path.join(H, "day_digest.py"), "--work", os.path.join(T, "empty"), "--date", D], capture_output=True).returncode == 0)
chk("дата не по формату — отказ", run("--date", "08.11.2026").returncode != 0)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
