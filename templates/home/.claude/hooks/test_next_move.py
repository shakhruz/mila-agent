#!/usr/bin/env python3
"""«Следующий ход» in send-guard: every answer ends with «Мой ход» and «Ваш ход»; «Мой ход» is one of three forms; what «comes by
itself» really stands in the schedule, at the time the answer names; a promise with a time needs a job; 2–3 buttons that are steps,
the first one green; «nothing needed, moving on» is refused; a part of a long answer says «(продолжение следует)»; and when the
check itself breaks the answer GOES OUT and the failure is written down. Time comes from MILA_CRON_NOW, counted from the run."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "send-guard.py"); REPO = os.path.join(H, "..", "..", "..", "..")
home = tempfile.mkdtemp(); work = os.path.join(home, "work"); CL = os.path.join(home, ".claude")
os.makedirs(os.path.join(CL, "channels/telegram")); os.makedirs(os.path.join(work, "schedule"))
json.dump({"groups": {"-1001": {}}, "allowFrom": ["555"]}, open(os.path.join(CL, "channels/telegram/access.json"), "w"))
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
env = dict(os.environ, HOME=home, OWNER_ID="111", MILA_WORK=work, CLAUDE_CONFIG_DIR=CL, MILA_CRON_NOW=NOW.isoformat(), PYTHONDONTWRITEBYTECODE="1")
for k in ("MILA_SCHEDULER_BEAT", "BARABAN_STATE", "XDG_STATE_HOME"): env.pop(k, None)
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
chk("правило — везде: в группе без строк тоже отказ", guard("Отчёт готов.", chat="-1001"), True, "Мой ход")
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
shutil.rmtree(home, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
