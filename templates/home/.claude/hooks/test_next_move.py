#!/usr/bin/env python3
"""«Следующий ход» in send-guard: every answer ends with «Мой ход» and «Ваш ход»; «Мой ход» is one of three forms; what «comes by
itself» really stands in the schedule, at the time the answer names; a promise with a time needs a job; 2–3 buttons that are steps,
the first one green; «nothing needed, moving on» is refused; a part of a long answer says «(продолжение следует)»; and when the
check itself breaks the answer GOES OUT and the failure is written down. Time comes from MILA_CRON_NOW, counted from the run."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "send-guard.py"); REPO = os.path.join(H, "..", "..", "..", "..")
home = tempfile.mkdtemp(); work = os.path.join(home, "work"); CL = os.path.join(home, ".claude")
os.makedirs(os.path.join(CL, "channels/telegram")); os.makedirs(os.path.join(work, "schedule"))
json.dump({"groups": {"-1001": {}, "-1002": {}, "-1003": {}}, "allowFrom": ["555"]}, open(os.path.join(CL, "channels/telegram/access.json"), "w"))
os.makedirs(os.path.join(home, ".claude", "hooks"), exist_ok=True)
json.dump(["555", "-1001", "-1003"], open(os.path.join(home, ".claude", "hooks", "internal-chats.json"), "w"))      # internal chats; the home names -1001 (work group) and 555 (a teammate) in MILA_HOD_CHATS, -1003 is internal but not named, -1002 is a client group
for s in ("raspisanie", "problemy", "dela", "pd-vault"):
    if os.path.isdir(os.path.join(REPO, "skills", s)): shutil.copytree(os.path.join(REPO, "skills", s), os.path.join(CL, "skills", s), ignore=shutil.ignore_patterns("__pycache__", "test_*"))
import zoneinfo
open(os.path.join(work, "USER.md"), "w", encoding="utf-8").write("Часовой пояс — Asia/Tashkent\n")      # the owner's zone: the guard, mila-cron and the service read this one line
NOW = dt.datetime.now(zoneinfo.ZoneInfo("Asia/Tashkent")).replace(hour=10, minute=0, second=0, microsecond=0)
if NOW.weekday() == 6: NOW += dt.timedelta(days=1)          # not a Sunday: «tomorrow 09:00» must be a plain next day
DAYS = ("понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье")
TOM = NOW + dt.timedelta(days=1)
jobs = {"jobs": [{"id": "отчёт за день", "cron": "0 9 * * *", "text": "отчёт", "enabled": True, "expires": (NOW + dt.timedelta(days=20)).date().isoformat()},
                 {"id": "вечерняя сводка", "cron": "30 18 * * *", "text": "сводка", "enabled": True, "expires": None},
                 {"id": "старая задача", "cron": "0 9 * * *", "text": "x", "enabled": True, "expires": (NOW - dt.timedelta(days=2)).date().isoformat()},
                 {"id": "выключенная", "cron": "0 9 * * *", "text": "x", "enabled": False, "expires": None}]}
J = os.path.join(work, "schedule", "jobs.json"); json.dump(jobs, open(J, "w"), ensure_ascii=False)
env = dict(os.environ, HOME=home, OWNER_ID="111", MILA_HOD_CHATS="-1001,555", MILA_WORK=work, CLAUDE_CONFIG_DIR=CL, MILA_CRON_NOW=NOW.isoformat(), PYTHONDONTWRITEBYTECODE="1")
for k in ("MILA_SCHEDULER_BEAT", "BARABAN_STATE", "XDG_STATE_HOME", "MILA_DEV_CHAT"): env.pop(k, None)
SLUG = os.path.basename(os.path.realpath(home)); BEATS = os.path.join(home, "state", "baraban")
def beat(age_s=0, name=None, folder=None, text=None):
    """The Scheduler's pass mark as the service leaves it: <state>/<home name>.beat with the time of the pass."""
    d = folder or BEATS; os.makedirs(d, exist_ok=True)
    t = dt.datetime.fromisoformat(env["MILA_CRON_NOW"]) - dt.timedelta(seconds=age_s)
    open(os.path.join(d, (name or SLUG) + ".beat"), "w").write(text if text is not None else t.isoformat(timespec="seconds") + "\n")
def no_beats():
    for d in (BEATS, os.path.join(home, ".local", "state", "mila", "baraban"), os.path.join(home, "beat-here")): shutil.rmtree(d, ignore_errors=True)
beat()
R = "mcp__plugin_mila-telegram_telegram__reply"
B2 = [[{"label": "Показать черновик", "choice": "show", "style": "success"}, {"label": "Не сейчас", "choice": "later"}]]
B3 = [[{"label": "Делай Б", "choice": "b", "style": "success"}, {"label": "Вариант А", "choice": "a"}, {"label": "Отложить", "choice": "wait"}]]
ok = n = 0
def guard(text, buttons=B2, chat="111", tool=R, **more):
    inp = {"tool_name": tool, "tool_input": dict({"chat_id": chat, "text": text}, **({"buttons": buttons} if buttons is not None else {}), **more)}
    r = subprocess.run([sys.executable, G], input=json.dumps(inp), capture_output=True, text=True, env=env, timeout=30)
    dec = ""
    if r.stdout.strip():
        try: h = json.loads(r.stdout)["hookSpecificOutput"]; dec = h["permissionDecision"]; why = h.get("permissionDecisionReason", "")
        except Exception: dec, why = "?", r.stdout
    else: why = ""
    return dec == "deny", why, r.returncode
def chk(name, got, want_deny, has=""):
    global ok, n
    deny, why, rc = got; good = deny == want_deny and (has in why)
    n += 1; ok += good; print(("✅ " if good else "❌ ") + name + ("" if good else "  ← deny=%s rc=%s %s" % (deny, rc, why[:300])))
MY1, MY3 = "Мой ход: делаю сейчас — свожу три листа в один.", "Мой ход: ничего не запущено — жду вашего решения."
YOU = "Ваш ход: советую посмотреть черновик письма."
def ans(my=MY3, you=YOU, head="Отчёт готов, файл в папке."): return head + "\n\n" + my + "\n" + you

# 1. the two lines
chk("обе строки, «ничего не запущено», две кнопки-шага — уходит", guard(ans()), False)
chk("«делаю сейчас», три кнопки — уходит", guard(ans(MY1), B3), False)
chk("без двух строк — отказ с подсказкой", guard("Отчёт готов."), True, "Мой ход")
chk("строки есть, но не последние — отказ", guard(MY3 + "\n" + YOU + "\nИ ещё одно."), True, "двумя строками")
chk("«Мой ход» есть, «Вашего» нет — отказ", guard("Готово.\n" + MY3), True, "двумя строками")
chk("строки в обратном порядке — отказ", guard("Готово.\n" + YOU + "\n" + MY3), True, "двумя строками")
chk("часть длинного ответа с «(продолжение следует)» — уходит без строк и кнопок", guard("Первая половина отчёта.\n(продолжение следует)", None), False)
chk("английские метки", guard("Done.\nMy move: nothing is running — waiting for you.\nYour move: I suggest looking at the draft."), False)
chk("узбекские метки", guard("Tayyor.\nMening yurishim: hech narsa ishga tushmagan — sizni kutyapman.\nSizning yurishingiz: qoralamani ko‘rishni maslahat beraman."), False)
chk("markdownv2 с экранированием («Мой ход\\:») — уходит", guard("Готово\\.\n*Мой ход\\:* ничего не запущено — жду вас\\.\n*Ваш ход\\:* советую посмотреть черновик\\.", format="markdownv2"), False)
chk("«Мой ход» не из трёх форм — отказ", guard(ans("Мой ход: работаю.")), True, "трёх форм")
chk("строка длиннее 200 знаков — отказ", guard(ans(MY1 + " " + "очень " * 40)), True, "200")
chk("рабочая группа, названная в MILA_HOD_CHATS: без строк — отказ", guard("Отчёт готов.", chat="-1001"), True, "Мой ход")
chk("в группе со строками — уходит", guard(ans(), chat="-1001"), False)
chk("правка сообщения (ход работы) — правило молчит", guard("идёт сборка…", None, tool="mcp__plugin_mila-telegram_telegram__edit_message"), False)

# 2. what «comes by itself» stands in the schedule, at that time
P = lambda t: "Мой ход: стоит в Планировщике — " + t
chk("задача есть, время из расписания — уходит", guard(ans(P("«отчёт за день», придёт завтра в 09:00."))), False)
chk("день недели верный — уходит", guard(ans(P("«отчёт за день», придёт в %s в 9:00." % DAYS[TOM.weekday()]))), False)
chk("сегодня в 18:30 — уходит", guard(ans(P("«вечерняя сводка», придёт сегодня в 18:30."))), False)
chk("задачи с таким именем нет — отказ", guard(ans(P("«недельный отчёт», придёт завтра в 09:00."))), True, "не стоит в расписании")
chk("задача истекла — отказ", guard(ans(P("«старая задача», придёт завтра в 09:00."))), True, "истекла")
chk("задача выключена — отказ", guard(ans(P("«выключенная», придёт завтра в 09:00."))), True, "выключена")
chk("время не то, что в расписании — отказ с настоящим сроком", guard(ans(P("«отчёт за день», придёт завтра в 10:00."))), True, "09:00")
chk("день недели не тот — отказ", guard(ans(P("«отчёт за день», придёт в %s в 09:00." % DAYS[(TOM.weekday() + 2) % 7]))), True, "день недели")
# «стоит в Планировщике» is a promise that something comes by itself: it is checked against the schedule in ANY chat. A chat the
# home did not name is free of the two lines and of the buttons — not of the truth of a promise once it is written.
for c, who in (("-1003", "внутренняя группа, не названная"), ("-1002", "клиентская группа")):
    chk(who + ": «стоит в Планировщике», а задача истекла — отказ", guard(ans(P("«старая задача», придёт завтра в 09:00.")), chat=c), True, "истекла")
    chk(who + ": «придёт сегодня», а срок завтра — отказ", guard(ans(P("«отчёт за день», придёт сегодня в 09:00.")), chat=c), True, "сегодня")
    chk(who + ": задачи с таким именем нет — отказ", guard(ans(P("«недельный отчёт», придёт завтра в 09:00.")), chat=c), True, "не стоит в расписании")
    chk(who + ": время не то, что в расписании — отказ", guard(ans(P("«отчёт за день», придёт завтра в 10:00.")), chat=c), True, "09:00")
    chk(who + ": задача есть и время верное, кнопок нет — уходит", guard(ans(P("«отчёт за день», придёт завтра в 09:00.")), None, chat=c), False)
    chk(who + ": пост без двух строк и без кнопок — уходит", guard("Доброе утро! Сегодня в выпуске три новости и один совет.", None, chat=c), False)
    chk(who + ": «делаю сейчас» двумя строками, без кнопок — уходит (форма не Планировщик — сверять нечего)", guard(ans(MY1), None, chat=c), False)
chk("«сегодня», а срок завтра — отказ", guard(ans(P("«отчёт за день», придёт сегодня в 09:00."))), True, "сегодня")
chk("без времени — отказ", guard(ans(P("«отчёт за день», придёт само."))), True, "временем")
chk("без имени задачи в кавычках — отказ", guard(ans(P("отчёт придёт завтра в 09:00."))), True, "кавычках")

# 3. a promise with a time needs a job
chk("«пришлю завтра» в тексте при «делаю сейчас» — отказ", guard(ans(MY1, head="Черновик пришлю завтра утром.")), True, "обещание со временем")
chk("«напомню в 18:00» при «ничего не запущено» — отказ", guard(ans(head="Напомню в 18:00.")), True, "обещание со временем")
chk("то же обещание, но задача стоит и названа — уходит", guard(ans(P("«отчёт за день», придёт завтра в 09:00."), head="Отчёт пришлю завтра.")), False)
chk("«вчера обещал прислать завтра» (не я, не будущее) — уходит", guard(ans(head="Партнёр вчера обещал прислать договор завтра.")), False)
chk("«придёт завтра» (не первое лицо) — уходит", guard(ans(head="Счёт от банка придёт завтра.")), False)

# 4. buttons: 2–3 steps, the first one green; several options are their own mode
chk("без кнопок — отказ", guard(ans(), None), True, "2–3 кнопки")
chk("одна кнопка — отказ", guard(ans(), [[{"label": "Показать", "choice": "a", "style": "success"}]]), True, "2–3 кнопки")
chk("четыре кнопки — отказ", guard(ans(), [B3[0] + [{"label": "Ещё", "choice": "x"}]]), True, "2–3 кнопки")
chk("первая не зелёная — отказ", guard(ans(), [[{"label": "Показать", "choice": "a"}, {"label": "Позже", "choice": "b"}]]), True, "зелёная")
chk("кнопка-ссылка в счёт не идёт: две кнопки-шага и ссылка — уходит", guard(ans(), [B2[0], [{"label": "Сайт", "url": "https://example.org"}]]), False)
chk("три кнопки-шага и ссылка — уходит: ссылка в счёт шагов не идёт", guard(ans(), [B3[0], [{"label": "Сайт", "url": "https://example.org"}]]), False)
chk("пустая кнопка «Принято» — отказ", guard(ans(), [[{"label": "Показать", "choice": "a", "style": "success"}, {"label": "Принято", "choice": "ok"}]]), True, "пустые")
chk("пустая кнопка «Подробнее» — отказ", guard(ans(), [[{"label": "Подробнее", "choice": "a", "style": "success"}, {"label": "Позже", "choice": "b"}]]), True, "пустые")
chk("выбор нескольких (multi) — свой режим, счёт кнопок не применяется", guard(ans(), [[{"label": "Отчёт", "choice": "r"}], [{"label": "Письмо", "choice": "m"}], [{"label": "Пост", "choice": "p"}], [{"label": "План", "choice": "pl"}]], multi=True), False)

# 5. «nothing needed, moving on»
chk("«Ваш ход: ничего не нужно» — отказ", guard(ans(you="Ваш ход: ничего не нужно, иду дальше.")), True, "рекомендация")
chk("«ничего не запущено — иду дальше» — отказ", guard(ans("Мой ход: ничего не запущено — иду дальше.")), True, "рекомендация")
chk("«продолжаю» в «Вашем ходе» — отказ", guard(ans(you="Ваш ход: продолжаю.")), True, "рекомендация")

# 5a. «(продолжение следует)» is a promise of the next part, not a way round the rule
F = os.path.join(work, "state", "next-move-fail.jsonl"); PJ = os.path.join(work, "problemy.jsonl"); WAIT = os.path.join(work, "state", "next-move-wait.json")
def notes(): return [json.loads(l) for l in open(F, encoding="utf-8")] if os.path.exists(F) else []
def problems(): return [json.loads(l) for l in open(PJ, encoding="utf-8")] if os.path.exists(PJ) else []
def at(minutes): env["MILA_CRON_NOW"] = (NOW + dt.timedelta(minutes=minutes)).isoformat(); beat()      # the service keeps passing as the clock moves
for f in (F, PJ, WAIT):
    if os.path.exists(f): os.remove(f)
at(0); chk("первая часть с «(продолжение следует)» — уходит, чат помечен «жду продолжение»", guard("Часть первая.\n(продолжение следует)", None, chat="555"), False)
n += 1; good = "555" in json.load(open(WAIT)); ok += good; print(("✅ " if good else "❌ ") + "метка ожидания записана по чату")
at(1); chk("следующий ответ в этот чат без двух строк — отказ: продолжение не отменяет правило", guard("Часть вторая, и всё.", None, chat="555"), True, "Мой ход")
chk("следующий ответ с двумя строками — уходит, метка снята, записей о проблемах нет", guard(ans(), chat="555"), False)
n += 1; good = "555" not in json.load(open(WAIT)) and notes() == [] and problems() == []; ok += good; print(("✅ " if good else "❌ ") + "после полного ответа ожидания нет и журнал чист" + ("" if good else "  ← %s %s" % (notes(), open(WAIT).read())))
at(2); guard("Снова часть.\n(продолжение следует)", None, chat="555")
at(3); chk("второе «(продолжение следует)» подряд — уходит, но записано проблемой", guard("И ещё часть.\n(продолжение следует)", None, chat="555"), False)
n += 1; good = [x["kind"] for x in notes()] == ["continuation-twice"] and len(problems()) == 1 and "подряд" in problems()[0]["что"]; ok += good
print(("✅ " if good else "❌ ") + "два продолжения подряд: строка в журнале сторожа и проблема" + ("" if good else "  ← %s %s" % (notes(), problems())))
at(4); guard(ans(), chat="555")                                   # the chat is closed properly
at(10); guard("Длинный отчёт, начало.\n(продолжение следует)", None, chat="-1001")
at(25); chk("через 15 минут ответ в ДРУГОЙ чат: брошенное продолжение записано проблемой", guard(ans(), chat="555"), False)
n += 1; good = [x["kind"] for x in notes()] == ["continuation-twice", "continuation-stale"] and notes()[-1]["chat_id"] == "-1001" and len(problems()) == 2 and "не пришла" in problems()[-1]["что"]; ok += good
print(("✅ " if good else "❌ ") + "продолжение без следующей части за 10 минут: строка и проблема, с чатом" + ("" if good else "  ← %s" % notes()))
n += 1; good = json.load(open(WAIT)) == {}; ok += good; print(("✅ " if good else "❌ ") + "брошенная метка снята — одна запись на случай, не на каждый ответ")
at(26); guard("Часть.\n(продолжение следует)", None, chat="555"); at(40)
chk("продолжение в том же чате пришло позже 10 минут — уходит, но опоздание записано", guard("Вторая часть.\n(продолжение следует)", None, chat="555"), False)
n += 1; good = notes()[-1]["kind"] == "continuation-twice" and "не пришла" in problems()[-1]["что"]; ok += good; print(("✅ " if good else "❌ ") + "опоздавшее продолжение названо своим именем" + ("" if good else "  ← %s" % problems()[-1]))
at(0)
for f in (F, PJ, WAIT):
    if os.path.exists(f): os.remove(f)

# 6. the check breaks → the answer goes out, the failure is written down
open(J, "w").write("{не json")
chk("расписание испорчено: форма 2 — отказ «не читается», сторож не падает", guard(ans(P("«отчёт за день», придёт завтра в 09:00."))), True, "не читается")
chk("расписание испорчено, но ответ без формы 2 — уходит", guard(ans()), False)
json.dump({"jobs": [{"id": "битая", "cron": "это не cron", "text": "x", "enabled": True}]}, open(J, "w"), ensure_ascii=False)
got = guard(ans(P("«битая», придёт завтра в 09:00.")))
chk("проверка хода сломалась внутри (cron не разбирается) — ответ УХОДИТ", got, False)
rows = notes()
n += 1; good = len(rows) == 1 and rows[0].get("kind") and "text" not in rows[0]; ok += good
print(("✅ " if good else "❌ ") + "сбой записан строкой в work/state/next-move-fail.jsonl (без текста ответа)" + ("" if good else "  ← %s" % rows))
pr = problems()
n += 1; good = len(pr) == 1 and pr[0].get("шаг") == "найдено" and "Следующего хода" in pr[0].get("что", "") and pr[0].get("улика", "").startswith("journal:state/next-move-fail.jsonl:"); ok += good
print(("✅ " if good else "❌ ") + "и проблемой в журнале проблем — с уликой на эту строку" + ("" if good else "  ← %s" % pr))
# ── «it stands in the Scheduler» is a promise only while the Scheduler passes for this home
json.dump(jobs, open(J, "w"), ensure_ascii=False)
at(0); OKMSG = ans(P("«отчёт за день», придёт завтра в 09:00.")); DEAD = "Планировщик здесь не работает"; fails_before = len(notes())
no_beats(); chk("Планировщик ни разу не проходил (ноутбук без таймера) — «стоит в Планировщике» отказ, с причиной и подсказкой", guard(OKMSG), True, "ни одного прохода")
chk("в отказе сказано прямо: Планировщик не работает", guard(OKMSG), True, DEAD)
chk("и что делать: сказать, что само не придёт, или запустить службу (доктор подскажет)", guard(OKMSG), True, "само не придёт, или запустите службу: python3 ~/.claude/hooks/doctor.py")
chk("при мёртвом Планировщике «ничего не запущено» уходит как раньше", guard(ans()), False)
chk("и «делаю сейчас» — тоже", guard(ans(MY1), B3), False)
beat(age_s=301); chk("последний проход 301 секунду назад — отказ, с давностью", guard(OKMSG), True, "5 мин назад")
beat(age_s=299); chk("проход 299 секунд назад — уходит", guard(OKMSG), False)
beat(age_s=3 * 86400); chk("служба стояла три дня — отказ", guard(OKMSG), True, DEAD)
no_beats(); beat(name="drugoj-dom"); beat(name="tretij-dom"); chk("в папке отметки двух ДРУГИХ домов, моей нет — отказ", guard(OKMSG), True, "ни одного прохода")
beat(age_s=4000); chk("моя отметка старая, чужие свежие — отказ: смотрю свою", guard(OKMSG), True, DEAD)
no_beats(); beat(name="mila"); chk("в папке одна отметка под другим именем (контейнер: один дом) — она и есть моя, уходит", guard(OKMSG), False)
no_beats(); beat(folder=os.path.join(home, ".local", "state", "mila", "baraban")); chk("отметка в папке состояния ноутбука (~/.local/state) — уходит", guard(OKMSG), False)
no_beats(); beat(folder=os.path.join(home, "beat-here")); chk("отметка в папке, о которой сторож не знает, — отказ", guard(OKMSG), True, DEAD)
env["MILA_SCHEDULER_BEAT"] = os.path.join(home, "beat-here"); chk("та же папка названа серверу переменной — уходит", guard(OKMSG), False); env.pop("MILA_SCHEDULER_BEAT")
no_beats(); beat(text="вчера\n"); chk("в отметке не время — отказ", guard(OKMSG), True, DEAD)
beat(text=dt.datetime.fromisoformat(env["MILA_CRON_NOW"]).replace(tzinfo=None).isoformat() + "\n"); chk("время в отметке без пояса — отказ", guard(OKMSG), True, DEAD)
beat(age_s=-600); chk("отметка из будущего (часы службы впереди на 10 минут) — уходит: служба жива", guard(OKMSG), False)
no_beats(); os.makedirs(BEATS); os.symlink(os.path.join(home, "nowhere"), os.path.join(BEATS, SLUG + ".beat")); chk("отметка — битая ссылка — отказ, без падения", guard(OKMSG), True, DEAD)
n += 1; good = len(notes()) == fails_before; ok += good
print(("✅ " if good else "❌ ") + "отказ по Планировщику — находка, а не сбой проверки: в журнал сбоев ничего не записано" + ("" if good else "  ← %s" % notes()[fails_before:]))
no_beats(); beat()
os.remove(J); os.makedirs(J)
chk("вместо расписания папка: форма 2 — отказ, остальное уходит", guard(ans(P("«отчёт за день», придёт завтра в 09:00."))), True, "не читается")
chk("другие сторожа живы рядом с ходом: извинение — отказ", guard(ans(head="Извините, не успела.")), True, "извинение")
chk("клиентская группа (не владелец и не команда): ответ без «Мой ход / Ваш ход» — уходит", guard("Виктор, вот три примера. Какой ближе к вашему делу?", B2, chat="-1002"), False)
chk("владелец: ответ без двух строк — по-прежнему отказ", guard("Готово, файл в папке.", B2, chat="111"), True, "Мой ход")
# 22.11.2026: the two lines are required only in the owner's private chat and in a work group the home names
chk("внутренняя группа, не названная в MILA_HOD_CHATS (есть в internal-chats.json): без двух строк — уходит", guard("Коллеги, сводка готова. Что смотрим первым?", B2, chat="-1003"), False)
def guard_env(text, chat, **e):
    global env; keep = env; env = dict({k: v for k, v in keep.items() if k not in ("MILA_HOD_CHATS", "MILA_DEV_CHAT")}, **e)
    try: return guard(text, B2, chat=chat)
    finally: env = keep
chk("ни MILA_DEV_CHAT, ни MILA_HOD_CHATS: в группе -1001 без двух строк — уходит", guard_env("Сводка готова. Что смотрим первым?", "-1001"), False)
chk("ни одной переменной: владельцу без двух строк — отказ", guard_env("Готово, файл в папке.", "111"), True, "Мой ход")
chk("MILA_DEV_CHAT=-1001: в этой группе без двух строк — отказ", guard_env("Сводка готова.", "-1001", MILA_DEV_CHAT="-1001"), True, "Мой ход")
chk("MILA_HOD_CHATS со списком и пробелами: вторая группа из списка без двух строк — отказ", guard_env("Сводка готова.", "-1003", MILA_HOD_CHATS="-1001, -1003"), True, "Мой ход")
chk("MILA_HOD_CHATS со списком: клиентская группа, которой в нём нет, — уходит", guard_env("Виктор, вот три примера. Какой ближе?", "-1002", MILA_HOD_CHATS="-1001, -1003"), False)
# clients and guests: no two labels, but a timed promise and the buttons are still checked
shutil.rmtree(J, ignore_errors=True); json.dump(jobs, open(J, "w"), ensure_ascii=False); no_beats(); beat()
C = "-1002"
chk("клиентская группа: «Пришлю завтра в 10:00 три варианта» без задачи Планировщика — отказ", guard("Виктор, пришлю завтра в 10:00 три варианта.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: обещание без времени — уходит", guard("Виктор, беру. Вернусь с результатом, как будет готово.", None, chat=C), False)
chk("клиентская группа: «вернусь через час» (времени по часам нет — сверить не с чем) — отказ", guard("Виктор, вернусь через час с ответом.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: обещание на время, где стоит задача Планировщика (18:30), — уходит", guard("Виктор, пришлю сегодня в 18:30 сводку.", None, chat=C), False)
chk("клиентская группа: на 09:00 есть живая задача (рядом выключенная и истёкшая на то же время) — уходит", guard("Виктор, пришлю завтра в 09:00 отчёт.", None, chat=C), False)
chk("клиентская группа: время 11:45, задачи на него нет — отказ", guard("Виктор, напишу завтра в 11:45.", None, chat=C), True, "обещание со временем")
no_beats()
chk("клиентская группа: задача есть, но Планировщик на машине не работает — отказ", guard("Виктор, пришлю сегодня в 18:30 сводку.", None, chat=C), True, "обещание со временем")
beat()
chk("клиентская группа: кнопка «Принято» — отказ", guard("Виктор, вот три примера.", [[{"label": "Смотреть", "choice": "s", "style": "success"}, {"label": "Принято", "choice": "ok"}]], chat=C), True, "не кнопки")
chk("клиентская группа: первая кнопка не зелёная — отказ", guard("Виктор, вот три примера.", [[{"label": "Смотреть", "choice": "s"}, {"label": "Позже", "choice": "l"}]], chat=C), True, "зелёная")
chk("клиентская группа: одна кнопка-шаг — отказ (2–3)", guard("Виктор, вот пример.", [[{"label": "Смотреть", "choice": "s", "style": "success"}]], chat=C), True, "2–3")
chk("клиентская группа: без кнопок вовсе — уходит", guard("Виктор, вот три примера. Какой ближе к вашему делу?", None, chat=C), False)
chk("клиентская группа: «через полчаса» и «через пару часов» — тоже обещание со временем", (all(guard("Виктор, напишу через %s." % w, None, chat=C)[0] for w in ("полчаса", "пару часов", "2 дня")), "", 0), True)
chk("клиентская группа: «пришлю к вечеру» и «пришлю к 18:00» без задачи — отказ", (all(guard("Виктор, пришлю %s подборку." % w, None, chat=C)[0] for w in ("к вечеру", "к 18:00")), "", 0), True)
for w in ("Пришлю примерно через час-два.", "Примерно через час-два пришлю подборку.", "Вернусь около 1–2 часов спустя — примерно через 1-2 часа.", "Отправлю ориентировочно через день-два."):
    chk("клиентская группа: вилка вместо времени — уходит: " + w[:38], guard("Виктор, беру. " + w, None, chat=C), False)
chk("клиентская группа: вилка стоит раньше, а при глаголе — точное «вечером»: обещание, отказ", guard("Виктор, примерно через час-два освобожусь и пришлю вечером три варианта.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: вилка и точное время через запятую — обещание, отказ", guard("Виктор, пришлю примерно через час-два, а договор — завтра в 10:00.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: вилка у первого глагола, точное время у второго — обещание, отказ", guard("Виктор, сделаю примерно за пару часов и пришлю в 18:05.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: «через час-два» без «примерно» — обещание, отказ", guard("Виктор, пришлю через час-два.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: вилка в одном предложении не прикрывает точное время в другом", guard("Виктор, пришлю примерно через час-два. А отчёт отправлю завтра в 11:45.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: «Отвечу к вечеру» — обещание, отказ", guard("Виктор, отвечу к вечеру.", None, chat=C), True, "обещание со временем")
chk("клиентская группа: время события людей («Встреча завтра в 15:00», «Эфир начнётся в 19:00») — не обещание, уходит", guard("Виктор, встреча завтра в 15:00 — вы с Амиром. Эфир начнётся в 19:00.", None, chat=C), False)
chk("владелец: вилка «примерно час-два» в ответе — не обещание", guard(ans(MY1, head="Сведу листы примерно через час-два — покажу, как будет готово.")), False)
chk("владелец: «вернусь через час» без задачи в «Моём ходе» — отказ (раньше «через час» без числа не ловилось)", guard(ans(MY1, head="Вернусь через час с ответом.")), True, "обещание со временем")
# OWNER_ID is not set: the only person in allowFrom is the owner — the rule stays for them
OWNERLESS = {k: v for k, v in env.items() if k != "OWNER_ID"}
os.remove(os.path.join(home, ".claude", "hooks", "internal-chats.json"))
def guard_ownerless(text, buttons=B2, chat="555"):
    r = subprocess.run([sys.executable, G], input=json.dumps({"tool_name": R, "tool_input": dict({"chat_id": chat, "text": text}, **({"buttons": buttons} if buttons is not None else {}))}),
                       capture_output=True, text=True, env=OWNERLESS, timeout=30)
    try: h = json.loads(r.stdout)["hookSpecificOutput"]; return h["permissionDecision"] == "deny", h.get("permissionDecisionReason", ""), r.returncode
    except Exception: return False, "", r.returncode
chk("OWNER_ID не задан, в allowFrom один человек — он владелец: ответ без двух строк — отказ", guard_ownerless("Готово, файл в папке."), True, "Мой ход")
chk("OWNER_ID не задан: клиентская группа — без двух строк уходит", guard_ownerless("Виктор, вот три примера.", None, chat="-1002"), False)
shutil.rmtree(home, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
