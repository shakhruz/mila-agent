#!/usr/bin/env python3
"""razvilki.py: a fork point with what was chosen, why and what to redo; a switch by the owner's word prints the redo list; a closed
point does not switch; a fork on anything behind a lock (money, the owner's name, sending, publishing, deleting) is refused — by the
mark and by the words — and the refusal stays in the journal; a word that means something else passes only with a stated reason.
Time from --now, counted from the run; the home of the test is a temp folder."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); os.umask(0o022)
env = {**os.environ, "MILA_WORK": T, "PYTHONDONTWRITEBYTECODE": "1"}
BASE = dt.datetime.now().astimezone() - dt.timedelta(days=20)
def at(m): return (BASE + dt.timedelta(minutes=m)).isoformat(timespec="seconds")
def R(*a, t=None):
    r = subprocess.run([sys.executable, "-I", os.path.join(H, "razvilki.py"), *a] + (["--now", at(t)] if t is not None else []), capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
L = os.path.join(T, "razvilki.jsonl")
def lines(): return [json.loads(l) for l in open(L, encoding="utf-8").read().splitlines() if l.startswith("{") and l.endswith("}")]
V = "А: таблица в одном файле|Б: три отдельных листа|В: подождать его ответа"
def add(*over, t=0, **kw):
    f = {"--vopros": "как собрать отчёт за неделю", "--varianty": V, "--vybrala": "Б", "--pochemu": "так он читал прошлые отчёты",
         "--peredelat": "свести три листа в один файл, около часа", "--ulika": "msg:abc:15"}
    f.update({"--" + k.replace("_", "-"): v for k, v in kw.items()})
    return R("add", *[x for k, v in f.items() if v is not None for x in (k, v)], *over, t=t)
try:
    rc, o = add(); chk("точка: номер R-0001, файл 600", rc == 0 and o == "R-0001" and oct(os.stat(L).st_mode & 0o777) == "0o600", o)
    r0 = lines()[0]; chk("в строке — вопрос, варианты по буквам, выбор, почему, что переделать, улика", r0["выбрано"] == "Б" and set(r0["варианты"]) == {"А", "Б", "В"} and r0["переделать"] and r0["улика"] == "msg:abc:15", r0)
    def bad(name, has="", t=1, **kw):
        rc, o = add(t=t, **kw); chk(name + " — отказ", rc != 0 and has in o, o)
    bad("без улики", ulika=None, has="улик")
    bad("улика текстом", ulika="он сказал", has="улик")
    bad("улика с пробелом внутри", ulika="link:https://example.org/a b", has="нет улики")
    bad("один вариант", varianty="А: только так", has="от двух до четырёх")
    bad("пять вариантов", varianty="А: a1|Б: b1|В: c1|Г: d1|Д: e1", has="от двух до четырёх")
    bad("буквы не по порядку", varianty="Б: сначала|А: потом", has="по порядку")
    bad("выбран вариант, которого нет", vybrala="Г", has="одна из букв")
    bad("нет «что переделать»", peredelat=" ", has="пусто")
    bad("нет «почему»", pochemu=None, has="пусто")
    bad("вопрос длиннее 160", vopros="в" * 161, has="160")
    bad("телефон в вопросе", vopros="как ответить клиенту +998 90 " + "123 45 67", has="личные данные")
    bad("две строки в «переделать»", peredelat="одно\nдругое", has="одной строкой")
    chk("после отказов формы в журнале одна строка", len(lines()) == 1, len(lines()))

    # behind a lock — never a fork
    for name, kw in (("оплата в вопросе", {"vopros": "когда оплатить хостинг"}), ("отправка в варианте", {"varianty": "А: отправить клиенту сейчас|Б: показать хозяину"}),
                     ("публикация в варианте", {"varianty": "А: опубликовать пост вечером|Б: утром"}), ("удаление в «переделать»", {"peredelat": "удалить старые файлы клиента"}),
                     ("от имени хозяина", {"vopros": "что ответить от имени хозяина партнёру"}), ("подпись", {"varianty": "А: подписать договор|Б: ждать"}),
                     ("перевод денег", {"vopros": "куда сделать перевод за рекламу"}), ("английское send", {"varianty": "А: send the offer now|Б: wait"}),
                     ("от вашего лица", {"vopros": "как ответить коллеге от вашего лица"}), ("пересылка", {"varianty": "А: переслать письмо партнёру|Б: ждать"}),
                     ("написать клиенту", {"varianty": "А: написать клиенту сегодня|Б: завтра"}), ("за вас", {"vopros": "что решить за вас по встрече"}),
                     ("ответить партнёру", {"peredelat": "ответить новому партнёру заново"}),
                     ("сообщить клиенту", {"vopros": "сообщить клиенту о задержке или подождать"}), ("уведомить партнёра", {"varianty": "А: уведомить партнёра сегодня|Б: в понедельник"}),
                     ("предупредить гостей", {"peredelat": "предупредить всех гостей заново"}), ("сообщу заказчику", {"varianty": "А: сообщу заказчику сама|Б: ждать"}), ("forward", {"varianty": "А: forward it|Б: keep"})):
        before = len(lines()); rc, o = add(t=5, **kw); last = lines()[-1]
        chk("под замком (%s) — отказ со словом «Согласование», отказ записан строкой" % name, rc != 0 and "Согласование" in o and len(lines()) == before + 1 and last["шаг"] == "отказ", o)
    before = len(lines()); rc, o = add("--zamok", t=6); chk("пометка --zamok — отказ, даже если слова чистые", rc != 0 and "под замком" in o and lines()[-1]["шаг"] == "отказ", o)
    rc, o = add("--zamok", t=6, ne_zamok="это только у меня"); chk("пометка --zamok сильнее оговорки", rc != 0, o)
    rc, o = add(t=7, vopros="на какой язык сделать перевод описания", ne_zamok="перевод текста, не денег"); last = lines()[-1]
    chk("слово значит другое и это сказано — точка записана вместе с оговоркой", rc == 0 and last["шаг"] == "точка" and last["не_замок"] == "перевод текста, не денег" and last["слово_замка"], (o, last))
    rc, o = add(t=7, vopros="на какой язык сделать перевод описания"); chk("то же без оговорки — отказ", rc != 0, o)
    rc, o = add(t=8, vopros="O" + "платить хостинг сейчас или позже"); chk("слово со смешанными алфавитами (латинская O в «оплатить») — отказ сам по себе", rc != 0 and "смешаны" in o, o)
    rc, o = add(t=8, vopros="какой шрифт для черн" + "o" + "вика"); chk("латинская буква внутри русского слова — отказ", rc != 0 and "смешаны" in o, o)
    for okw in ("сотрудник делает сводку или я", "написать отчёт таблицей или текстом", "ответ хозяину коротко или подробно", "Telegram или почта для моих заметок", "расчёт по часам или по дням", "подписка на канал в подборке или без", "дизайн карточки светлый или тёмный", "signal в подборке или нет", "сообщение клиента в сводку или отдельно", "уведомления гостей показывать в отчёте или нет", "предупреждение партнёра учесть в плане или нет"):
        rc, o = add(t=8, vopros=okw); chk("обычное слово не принято за замок: «%s»" % okw[:24], rc == 0, o)

    # switch by the owner's word, done
    rc, o = R("switch", "R-0001", "--na", "А", "--ulika", "file:x.md", t=20); chk("смена курса с уликой не его сообщением — отказ", rc != 0 and "msg:" in o, o)
    rc, o = R("switch", "R-0001", "--na", "А", t=20); chk("смена без улики — отказ", rc != 0, o)
    rc, o = R("switch", "R-0001", "--na", "Б", "--ulika", "msg:abc:20", t=20); chk("смена на тот же вариант — отказ", rc != 0 and "уже иду" in o, o)
    rc, o = R("switch", "R-0001", "--na", "Г", "--ulika", "msg:abc:20", t=20); chk("смена на вариант, которого нет, — отказ", rc != 0 and "одна из букв" in o, o)
    rc, o = R("switch", "R-0099", "--na", "А", "--ulika", "msg:abc:20", t=20); chk("чужой номер — отказ", rc != 0 and "нет" in o, o)
    rc, o = R("switch", "../x", "--na", "А", "--ulika", "msg:abc:20", t=20); chk("номер не по форме — отказ", rc != 0, o)
    rc, o = R("switch", "R-0001", "--na", "А", "--ulika", "msg:abc:20", t=21)
    chk("смена по его сообщению: Б → А, напечатано, что переделать", rc == 0 and "Б → А" in o and "свести три листа" in o, o)
    rc, o = R("list", "--open"); chk("list: иду по А, одна смена, «при смене» на месте", "R-0001" in o and "иду по А" in o and "смен 1" in o, o)
    rc, o = R("switch", "R-0001", "--na", "В", "--ulika", "msg:abc:22", t=22); chk("вторая смена, пока точка открыта, — можно", rc == 0 and "А → В" in o, o)
    rc, o = R("done", "R-0001", "--prichina", " ", t=23); chk("закрыть без причины — отказ", rc != 0, o)
    rc, o = R("done", "R-0001", "--prichina", "хозяин принял отчёт", t=24); chk("закрыта на варианте В", rc == 0 and "В" in o, o)
    rc, o = R("switch", "R-0001", "--na", "А", "--ulika", "msg:abc:25", t=25); chk("закрытая точка курс не меняет", rc != 0 and "закрыта" in o, o)
    rc, o = R("done", "R-0001", "--prichina", "ещё раз", t=26); chk("закрыть дважды — отказ", rc != 0, o)
    rc, o = R("list", "--open"); chk("list --open: закрытой нет, открытые есть", "R-0001" not in o and "иду по" in o, o)
    rc, o = R("itog", "--days", "30", "--json", t=30); d = json.loads(o)
    chk("итог: точки, открытые, смены курса, закрытые, отказы «под замком»", d["смен_курса"] == 2 and d["закрыто"] == 1 and d["отказов_замка"] == 21 and d["точек"] == d["открыто"] + 1, d)

    # a broken line, numbers by max+1 under the lock, two writers
    open(L, "a", encoding="utf-8").write('{"n": "R-0050", "ts": "' + at(40) + '", "шаг": "точка", "обрыв\n' + "не json\n")
    open(L, "a", encoding="utf-8").write(json.dumps({"n": "R-0060", "ts": at(41), "шаг": "точка", "вопрос": "далеко впереди", "варианты": {"А": "a", "Б": "b"}, "выбрано": "А", "переделать": "x", "улика": "msg:z:1"}, ensure_ascii=False) + "\n")
    ps = [subprocess.Popen([sys.executable, "-I", os.path.join(H, "razvilki.py"), "add", "--vopros", "одновременная точка %d" % i, "--varianty", "А: так|Б: иначе", "--vybrala", "А", "--pochemu", "быстрее",
                            "--peredelat", "сделать иначе", "--ulika", "msg:p:%d" % i, "--now", at(50)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for i in range(10)]
    outs = sorted(p.communicate()[0].strip() for p in ps)
    chk("10 писателей разом: 10 номеров подряд после наибольшего (R-0061…)", outs == ["R-%04d" % (61 + i) for i in range(10)], outs)
    rc, o = R("list"); chk("битая строка чтению не мешает", rc == 0 and "R-0070" in o, o[-160:])
    import fcntl, time
    hold = open(L, "a"); fcntl.flock(hold, fcntl.LOCK_EX)   # the journal is busy: both writers wait; without the lock both would have read the same last number
    ps = [subprocess.Popen([sys.executable, "-I", os.path.join(H, "razvilki.py"), "add", "--vopros", "точка при занятом журнале %d" % i, "--varianty", "А: так|Б: иначе", "--vybrala", "А", "--pochemu", "быстрее",
                            "--peredelat", "сделать иначе", "--ulika", "msg:q:%d" % i, "--now", at(60)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env) for i in range(2)]
    time.sleep(1.5); busy = [p.poll() for p in ps]; fcntl.flock(hold, fcntl.LOCK_UN); hold.close()
    outs = sorted(p.communicate(timeout=30)[0].strip() for p in ps)
    chk("журнал занят — оба писателя ждут; после — два разных номера подряд", busy == [None, None] and outs == ["R-0071", "R-0072"], (busy, outs))
    os.remove(L); rc, o = R("list"); chk("журнала нет — «развилок нет», не падение", rc == 0 and "нет" in o, o)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
