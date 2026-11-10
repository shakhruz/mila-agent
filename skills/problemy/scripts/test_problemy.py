#!/usr/bin/env python3
"""problemy.py: the whole circle of one problem; every refusal; the third case of one class in one place is not closed by a promise
(a reopen and a new problem — one count, «другое» counts too); two writers; a broken line; file 600. Time comes from --now, counted
from the moment of the run — no wall-clock dates in the fixtures. The home of the test is a temp folder, removed at the end."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); env = {**os.environ, "MILA_WORK": T, "PYTHONDONTWRITEBYTECODE": "1"}
os.umask(0o022)   # an open umask: the journal must be 600 by its own mode, not by the caller's umask
BASE = dt.datetime.now().astimezone() - dt.timedelta(days=30)
def at(minutes): return (BASE + dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")
def P(*a, t=None):
    r = subprocess.run([sys.executable, "-I", os.path.join(H, "problemy.py"), *a] + (["--now", at(t)] if t is not None else []), capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
L = os.path.join(T, "problemy.jsonl")
def lines(): return [json.loads(l) for l in open(L, encoding="utf-8").read().splitlines() if l.strip().startswith("{") and l.strip().endswith("}")]
try:
    for f in ("note.md", "fix.md", "run.log"): open(os.path.join(T, f), "w").write("x\n")
    ADD = ("add", "--chto", "отчёт ушёл без числа проверок", "--gde", "личка", "--kto-nashel", "хозяин", "--ulika", "msg:abc:15")

    # 1. the whole circle
    rc, o = P(*ADD, t=0); chk("найдено: номер P-0001, файл 600", rc == 0 and o == "P-0001" and oct(os.stat(L).st_mode & 0o777) == "0o600", o)
    rc, o = P("why", "P-0001", "--prichina", "число взято из памяти, не из прогона", "--klass", "проверка", t=1); chk("причина с классом", rc == 0, o)
    rc, o = P("fix", "P-0001", "--pravka", "число только из журнала прогона", "--vid", "обещание", "--ulika", "msg:abc:16", t=2); chk("правка-обещание с уликой msg", rc == 0, o)
    rc, o = P("close", "P-0001", t=3); chk("закрыть без «проверено» — отказ", rc != 0 and "проверен" in o, o)
    rc, o = P("verify", "P-0001", "--ulika", "msg:abc:16", t=4); chk("проверка той же уликой, что правка, — отказ", rc != 0 and "не та же" in o, o)
    rc, o = P("verify", "P-0001", "--ulika", "file:run.log", t=2); chk("проверка не позже правки по времени — отказ", rc != 0 and "позже" in o, o)
    rc, o = P("verify", "P-0001", "--ulika", "file:run.log", t=1); chk("проверка раньше правки — отказ", rc != 0 and "позже" in o, o)
    rc, o = P("verify", "P-0001", "--ulika", "file:run.log", t=5); chk("проверено: другая улика, позже правки", rc == 0, o)
    rc, o = P("verify", "P-0001", "--ulika", "file:note.md", t=6); chk("повтор той же ступени — отказ", rc != 0, o)
    rc, o = P("close", "P-0001", t=7); chk("закрыто", rc == 0, o)
    chk("в журнале пять строк круга по порядку", [r["шаг"] for r in lines()] == ["найдено", "причина", "правка", "проверено", "закрыто"], lines())

    # 2. refusals at «найдено»
    def bad(name, *a, has=""):
        rc, o = P(*a, t=10); chk(name + " — отказ", rc != 0 and has in o, o)
    bad("без улики", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "сама")
    bad("улика текстом", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "он сказал", has="улик")
    bad("улика с пробелом внутри", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "link:https://example.org/a b", has="улик")
    bad("улика — файл вне work", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "file:../../etc/hostname", has="не сходится")
    bad("улика — файла нет", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "file:net.md", has="не сходится")
    bad("место не из списка", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "чатик", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="место")
    bad("кто нашёл не из списка", "add", "--chto", "ответ ушёл не в тот чат", "--gde", "группа", "--kto-nashel", "кто-то", "--ulika", "msg:a:1", has="кто")
    bad("общее слово вместо факта", "add", "--chto", "Ошибка", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="факт")
    bad("пустое «что»", "add", "--chto", " ", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="пусто")
    bad("«что» длиннее 160", "add", "--chto", "д" * 161, "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="160")
    bad("«что» в две строки", "add", "--chto", "одно\nдругое", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="одной строкой")
    PH = "+998 90 " + "123 45 67"
    bad("телефон в «что»", "add", "--chto", "клиент " + PH + " не получил ответ", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="личные данные")
    bad("@ник в «что»", "add", "--chto", "написала @ivan_k не то", "--gde", "группа", "--kto-nashel", "сама", "--ulika", "msg:a:1", has="личные данные")
    chk("после отказов в журнале по-прежнему пять строк", len(lines()) == 5, len(lines()))

    # 3. order of stages, foreign numbers
    rc, o = P("add", "--chto", "напоминание пришло на час позже", "--gde", "расписание", "--kto-nashel", "человек", "--ulika", "msg:a:2", t=20); chk("вторая проблема — P-0002", o == "P-0002", o)
    rc, o = P("fix", "P-0002", "--pravka", "пояс из USER.md", "--vid", "настройка", "--ulika", "file:fix.md", t=21); chk("правка без причины — отказ", rc != 0 and "после причины" in o, o)
    rc, o = P("why", "P-0009", "--prichina", "x y", "--klass", "срок", t=21); chk("чужой номер — отказ", rc != 0 and "нет" in o, o)
    rc, o = P("why", "../x", "--prichina", "x y", "--klass", "срок", t=21); chk("номер не по форме — отказ", rc != 0, o)
    rc, o = P("why", "P-0002", "--prichina", "пояс сервера вместо пояса человека", "--klass", "время", t=21); chk("класс не из списка — отказ", rc != 0 and "класс" in o, o)
    rc, o = P("why", "P-0002", "--prichina", "пояс сервера вместо пояса человека", "--klass", "срок", t=22); chk("причина P-0002", rc == 0, o)
    rc, o = P("fix", "P-0002", "--pravka", "пояс из USER.md", "--vid", "настройка", "--ulika", "msg:a:3", t=23); chk("правка-настройка с уликой msg — отказ (нужен файл или коммит)", rc != 0 and "file:" in o, o)
    rc, o = P("fix", "P-0002", "--pravka", "пояс из USER.md", "--vid", "совет", "--ulika", "file:fix.md", t=23); chk("вид правки не из списка — отказ", rc != 0 and "вид" in o, o)
    rc, o = P("fix", "P-0002", "--pravka", "пояс из USER.md", "--vid", "настройка", "--ulika", "file:fix.md", t=24); chk("правка-настройка с файлом", rc == 0, o)
    rc, o = P("verify", "P-0002", "--ulika", "msg:a:4", t=25); chk("для настройки проверка — повторённый случай (msg)", rc == 0, o)
    rc, o = P("reopen", "P-0002", "--ulika", "msg:a:5", t=26); chk("повтор у незакрытой — отказ", rc != 0 and "закрытой" in o, o)
    rc, o = P("close", "P-0002", t=27); chk("P-0002 закрыта", rc == 0, o)

    # 4. the third case: a reopen and a new problem are one count; a promise is refused, the refusal stays in the journal
    rc, o = P("reopen", "P-0001", "--ulika", "msg:abc:30", t=40); chk("повтор закрытой P-0001 — случай №2", rc == 0 and "№2" in o, o)
    rc, o = P("why", "P-0001", "--prichina", "снова число из памяти", "--klass", "проверка", t=41); chk("причина после повтора — заново", rc == 0, o)
    rc, o = P("fix", "P-0001", "--pravka", "буду сверять", "--vid", "обещание", "--ulika", "msg:abc:31", t=42); chk("второй случай обещанием — можно", rc == 0, o)
    P("verify", "P-0001", "--ulika", "file:run.log", t=43); P("close", "P-0001", t=44)
    rc, o = P("add", "--chto", "итог дня ушёл с числом из вчерашнего прогона", "--gde", "личка", "--kto-nashel", "сама", "--ulika", "msg:abc:40", t=50); n3 = o
    P("why", n3, "--prichina", "число не из свежего журнала", "--klass", "проверка", t=51)
    before = len(lines())
    rc, o = P("fix", n3, "--pravka", "буду внимательнее", "--vid", "обещание", "--ulika", "msg:abc:41", t=52)
    chk("третий случай (повтор + новая) обещанием — отказ со словом «механизм»", rc != 0 and "механизм" in o, o)
    last = lines()[-1]; chk("отказ записан строкой: класс, место, число случаев", len(lines()) == before + 1 and last["шаг"] == "отказ" and last["случаев"] == 3 and last["место"] == "личка", last)
    rc, o = P("reclass", n3, "--prichina", "на самом деле не успела", "--klass", "проверка", t=53); chk("смена класса на тот же — отказ", rc != 0, o)
    rc, o = P("reclass", n3, "--prichina", "на самом деле не успела", "--klass", "срок", t=53); last = lines()[-1]
    chk("смена класса после отказа — строкой с пометкой и прежним классом", rc == 0 and last["шаг"] == "переклассификация" and last["после_отказа"] is True and last["был"] == "проверка", last)
    rc, o = P("itog", "--days", "60", "--json", t=54); d = json.loads(o)
    chk("итог (json) видит отказ и смену класса после него", d.get("отказы_третьего_раза") == 1 and d.get("смен_класса_после_отказа") == 1, d)
    before = len(lines()); rc, o = P("fix", n3, "--pravka", "буду внимательнее", "--vid", "обещание", "--ulika", "msg:abc:41", t=54)
    chk("после отказа и смены класса обещание по этому номеру закрыто; второй отказ тоже записан", rc != 0 and "механизм" in o and len(lines()) == before + 1 and lines()[-1]["шаг"] == "отказ", o)
    rc, o = P("povtory", "--json"); d = json.loads(o)
    chk("povtory считает и класс до смены: проверка · личка — 3", {"класс": "проверка", "место": "личка", "случаев": 3} in d, d)
    rc, o = P("itog", "--days", "60", t=54); chk("итог строкой называет отказы и смены класса", "отказов третьего раза 2" in o and "смен класса после отказа 1" in o and "нужен механизм: 1" in o, o)
    P("reclass", n3, "--prichina", "число не из свежего журнала", "--klass", "проверка", t=55)
    rc, o = P("fix", n3, "--pravka", "скрипт отчёта берёт число из журнала прогона", "--vid", "проверка", "--ulika", "file:fix.md", t=56); chk("третий случай механизмом — принят", rc == 0, o)
    rc, o = P("povtory", "--json", t=57); d = json.loads(o); chk("povtory: проверка · личка — 3 случая; срок · личка (класс побывал) — меньше трёх, не в списке", [x for x in d if "класс" in x] == [{"класс": "проверка", "место": "личка", "случаев": 3}], d)
    chk("povtory: место личка — случаи разных классов за 14 дней отдельной строкой, не отказом", [x for x in d if "классы" in x] == [{"место": "личка", "случаев": 3, "классы": ["проверка", "срок"], "за_дней": 14}], d)
    rc, o = P("povtory", "--json", t=57 + 60 * 24 * 15); d = json.loads(o); chk("через 15 дней строка места уходит, правило класса остаётся", [x for x in d if "классы" in x] == [] and len(d) == 1, d)
    rc, o = P("add", "--chto", "тот же факт под другим классом", "--gde", "личка", "--kto-nashel", "сама", "--ulika", "msg:q:1", t=58); nq = o
    P("why", nq, "--prichina", "назвала иначе", "--klass", "текст", t=58); rc, o = P("fix", nq, "--pravka", "буду следить", "--vid", "обещание", "--ulika", "msg:q:2", t=59)
    rc2, o2 = P("povtory", t=59)
    chk("новый номер с другим классом в том же месте: обещание проходит, место видно строкой «посмотрите»", rc == 0 and "место личка: 4 случаев разных классов за 14 дней (проверка, срок, текст)" in o2, (o, o2))
    for i in range(3):
        rc, o = P("add", "--chto", "случай без ясного места номер %d" % i, "--gde", "другое", "--kto-nashel", "сама", "--ulika", "msg:d:%d" % i, t=60 + i); nd = o
        P("why", nd, "--prichina", "не разобралась", "--klass", "другое", t=63 + i)
    rc, o = P("fix", nd, "--pravka", "разберусь", "--vid", "обещание", "--ulika", "msg:d:9", t=70); chk("третье «другое» в месте «другое» обещанием — отказ", rc != 0 and "механизм" in o, o)
    rc, o = P("povtory", t=71); chk("три случая одного класса — строка правила, без второй строки «место»", "другое · другое: 3 случаев — нужен механизм" in o and "место другое" not in o, o)

    # 5. two writers at once, a broken line, numbers by max+1
    open(L, "a", encoding="utf-8").write('{"n": "P-0050", "ts": "' + at(80) + '", "шаг": "найдено", "что": "обрыв\n')
    open(L, "a", encoding="utf-8").write("не json вовсе\n")
    open(L, "a", encoding="utf-8").write(json.dumps({"n": "P-0050", "ts": at(81), "шаг": "найдено", "что": "строка с номером далеко впереди", "место": "другое", "кто": "сама", "улика": "msg:z:1"}, ensure_ascii=False) + "\n")
    top = max(int(r["n"][2:]) for r in lines())
    ps = [subprocess.Popen([sys.executable, "-I", os.path.join(H, "problemy.py"), "add", "--chto", "одновременная запись %d" % i, "--gde", "инструмент", "--kto-nashel", "проверка",
                            "--ulika", "msg:p:%d" % i, "--now", at(90)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for i in range(12)]
    outs = [p.communicate()[0].strip() for p in ps]
    chk("12 писателей разом: 12 разных номеров подряд после наибольшего", sorted(outs) == ["P-%04d" % (top + 1 + i) for i in range(12)], outs)
    raw = open(L, encoding="utf-8").read().splitlines()
    chk("строки целые: всё после битых — разбираемый json", all(l.startswith("{") and json.loads(l) for l in raw[-12:]), raw[-3:])
    rc, o = P("list", "--open"); chk("битая строка в середине не мешает чтению", rc == 0 and "P-%04d" % (top + 12) in o, o[-200:])
    rc, o = P("itog", "--days", "60", t=100); chk("итог одной строкой с числами", rc == 0 and "найдено" in o and "нужен механизм: 2" in o, o)
    rc, o = P("itog", "--days", "7", "--json", t=100 + 60 * 24 * 20); d = json.loads(o)
    chk("через 20 дней: открытые старше 7 дней посчитаны, за неделю найдено 0", d["найдено"] == 0 and d["открыто_старше_7_дней"] == d["открыто"] > 0, d)
    os.remove(L); rc, o = P("list"); chk("журнала нет — «проблем нет», не падение", rc == 0 and "нет" in o, o)
    rc, o = P("close", "P-0001", t=1); chk("журнала нет — закрытие отказ, файл не испорчен", rc != 0 and (not os.path.exists(L) or os.path.getsize(L) == 0), o)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
