#!/usr/bin/env python3
"""cronspec — расчёт сроков Планировщика: разбор, ближайший срок, последний срок, лимит частоты. Usage: python3 test_cronspec.py"""
import datetime, os, sys, zoneinfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cronspec as C

ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
TZ = zoneinfo.ZoneInfo("Asia/Tashkent")
D = lambda *a: datetime.datetime(*a, tzinfo=TZ)
def bad(expr, word):
    try: C.parse(expr); return False
    except ValueError as e: return word in str(e)

# разбор и отказы
chk("ежедневно 19:30 — разбирается", C.parse("30 19 * * *").next_after(D(2026, 10, 25, 12, 0)) == D(2026, 10, 25, 19, 30))
chk("4 поля — отказ с понятной причиной", bad("30 19 * *", "5 полей"))
chk("минута 60 — отказ", bad("60 * * * *", "вне"))
chk("диапазон наоборот — отказ", bad("0 10-8 * * *", "наоборот"))
chk("имя дня (mon) — отказ, только числа", bad("0 9 * * mon", "только числа"))
chk("каждую минуту — отказ (лимит 5 мин)", bad("* * * * *", "чаще раза в 5"))
chk("*/2 — отказ", bad("*/2 * * * *", "чаще"))
chk("*/5 — можно", C.parse("*/5 * * * *").min_step_minutes() == 5)
chk("31 февраля — отказ «такого дня не бывает»", bad("0 9 31 2 *", "не бывает"))
chk("шаг /0 — отказ", bad("*/0 * * * *", "шаг"))
chk("не строка — отказ", bad(None, "строка"))
chk("пустой элемент списка — отказ", bad("0,,30 9 * * *", "пустой"))

# ближайший срок
s = C.parse("0 9 * * 1-5")
chk("будни 09:00: из пт 10:00 → пн 09:00", s.next_after(D(2026, 10, 23, 10, 0)) == D(2026, 10, 26, 9, 0))
chk("строго после: ровно в 09:00 → следующий день", s.next_after(D(2026, 10, 26, 9, 0)) == D(2026, 10, 27, 9, 0))
chk("воскресенье — 0 и 7 одно и то же", C.parse("0 9 * * 0").next_after(D(2026, 10, 25, 10, 0)) == C.parse("0 9 * * 7").next_after(D(2026, 10, 25, 10, 0)) == D(2026, 11, 1, 9, 0))
chk("конец месяца: 31-е → из 30.11 в 31.12", C.parse("0 8 31 * *").next_after(D(2026, 11, 30, 0, 0)) == D(2026, 12, 31, 8, 0))
chk("29.02 — ближайший 2028", C.parse("0 12 29 2 *").next_after(D(2026, 3, 1, 0, 0)) == D(2028, 2, 29, 12, 0))
chk("день месяца ИЛИ день недели (оба заданы): 1-е или пн", C.parse("0 9 1 * 1").next_after(D(2026, 10, 27, 0, 0)) == D(2026, 11, 1, 9, 0))
chk("список и шаг: 10-50/20 → 10, 30, 50", sorted(C.parse("10-50/20 9 * * *").mins) == [10, 30, 50])
chk("через полночь: 23:55 → 00:05 следующего дня", C.parse("5 0 * * *").next_after(D(2026, 10, 25, 23, 55)) == D(2026, 10, 26, 0, 5))
chk("через год: 1 января", C.parse("0 0 1 1 *").next_after(D(2026, 12, 31, 23, 59)) == D(2027, 1, 1, 0, 0))
chk("пояс хозяина: срок в Asia/Tashkent (UTC+5)", C.parse("30 19 * * *").next_after(D(2026, 10, 25, 12, 0)).utcoffset() == datetime.timedelta(hours=5))
chk("пятница 16:30 (ритуал «пт»)", C.parse("30 16 * * 5").next_after(D(2026, 10, 25, 9, 0)) == D(2026, 10, 30, 16, 30))

# последний срок ≤ сейчас (созрел ли)
e = C.parse("30 19 * * *")
chk("последний ≤ 20:00 — сегодня 19:30", e.last_at_or_before(D(2026, 10, 25, 20, 0)) == D(2026, 10, 25, 19, 30))
chk("последний ≤ 19:30 — ровно он (включительно)", e.last_at_or_before(D(2026, 10, 25, 19, 30)) == D(2026, 10, 25, 19, 30))
chk("последний ≤ 10:00 — вчера 19:30", e.last_at_or_before(D(2026, 10, 25, 10, 0)) == D(2026, 10, 24, 19, 30))
chk("после простоя 3 дня — последний один (догоняющий один, не пачка)", e.last_at_or_before(D(2026, 10, 28, 20, 0)) == D(2026, 10, 28, 19, 30))
chk("ежегодный 1.01: последний ≤ 25.10.2026 — 01.01.2026", C.parse("0 0 1 1 *").last_at_or_before(D(2026, 10, 25, 0, 0)) == D(2026, 1, 1, 0, 0))

# шаг для лимита
chk("min_step: 9:00 и 9:03 → 3 (и отказ при разборе)", bad("0,3 9 * * *", "шаг 3"))
chk("min_step: раз в сутки → 1440", C.parse("0 9 * * *").min_step_minutes() == 1440)
chk("min_step: 23:58 и 00:01 через полночь → отказ", bad("58 23 * * *", "x") is False and bad("1,58 0,23 * * *", "чаще"))
# ── the owner's zone: one rule for the service, mila-cron and the send guard
import os, shutil, tempfile, zoneinfo
chk("пояс: строка USER.md", str(C.owner_tz("Имя — Иван\nЧасовой пояс — Europe/Berlin\n")) == "Europe/Berlin")
chk("пояс: строки нет — Asia/Tashkent, а не пояс машины", str(C.owner_tz("Имя — Иван\n")) == "Asia/Tashkent" and str(C.owner_tz("")) == "Asia/Tashkent" and str(C.owner_tz(None)) == "Asia/Tashkent")
chk("пояс: несуществующий в строке — Asia/Tashkent, без падения", str(C.owner_tz("Часовой пояс — Mars/Olympus\n")) == "Asia/Tashkent")
chk("пояс: дефис вместо тире тоже читается", str(C.owner_tz("Часовой пояс - America/New_York")) == "America/New_York")
# ── the pass mark of the service: which file is this home's, and how fresh it is
T = tempfile.mkdtemp(prefix="beat-"); home = os.path.join(T, "ivan"); os.makedirs(home)
t0 = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Tashkent"))
def beat(folder, name, when=t0, text=None):
    os.makedirs(folder, exist_ok=True); open(os.path.join(folder, name + ".beat"), "w").write(text if text is not None else when.isoformat() + "\n")
E = {}
chk("отметок нет нигде — None", C.last_beat(home, E) is None)
st = os.path.join(home, "state", "baraban"); beat(st, "ivan")
chk("контейнер: ~/state/baraban/<дом>.beat", C.last_beat(home, E) == t0)
xdg = os.path.join(home, ".local", "state", "mila", "baraban"); beat(xdg, "ivan", t0 + datetime.timedelta(minutes=3))
chk("ноутбук: ~/.local/state/mila/baraban; из двух папок берётся свежая", C.last_beat(home, E) == t0 + datetime.timedelta(minutes=3))
chk("XDG_STATE_HOME меняет папку ноутбука", C.last_beat(home, {"XDG_STATE_HOME": os.path.join(T, "nowhere")}) == t0)
far = os.path.join(T, "far"); beat(far, "ivan", t0 + datetime.timedelta(minutes=9))
chk("папка, о которой правило не знает, не читается; названная MILA_SCHEDULER_BEAT или BARABAN_STATE — читается",
    C.last_beat(home, E) == t0 + datetime.timedelta(minutes=3) and C.last_beat(home, {"MILA_SCHEDULER_BEAT": far}) == t0 + datetime.timedelta(minutes=9) and C.last_beat(home, {"BARABAN_STATE": far}) == t0 + datetime.timedelta(minutes=9))
shutil.rmtree(st); shutil.rmtree(xdg); beat(st, "petr"); beat(st, "anna")
chk("в папке отметки двух других домов — не мои: None", C.last_beat(home, E) is None)
beat(st, "ivan", t0 - datetime.timedelta(days=1)); chk("есть моя — беру её, хоть чужие свежее", C.last_beat(home, E) == t0 - datetime.timedelta(days=1))
shutil.rmtree(st); beat(st, "mila"); chk("одна отметка под другим именем (один дом в папке) — моя", C.last_beat(home, E) == t0)
for bad_text, what in (("вчера", "не время"), ("", "пусто"), ("2026-05-04T09:00:00", "время без пояса")):
    beat(st, "mila", text=bad_text); chk("в отметке %s — None" % what, C.last_beat(home, E) is None)
os.remove(os.path.join(st, "mila.beat")); os.symlink(os.path.join(T, "gone"), os.path.join(st, "mila.beat")); chk("отметка — битая ссылка — None, без падения", C.last_beat(home, E) is None)
link = os.path.join(T, "link-home"); os.symlink(home, link); os.remove(os.path.join(st, "mila.beat")); beat(st, "petr"); beat(st, "ivan")
chk("дом назван через ссылку — имя отметки по настоящей папке", C.last_beat(link, E) == t0)
chk("свежесть — пять минут", C.BEAT_FRESH == 300)
shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
