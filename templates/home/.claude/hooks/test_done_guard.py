#!/usr/bin/env python3
"""Тест done-guard.py на снимках журнала в живом формате Claude Code (строка на блок, у блоков одного ответа модели один message.id;
tool_result — строкой user). Каждый случай: exit 0, решение «deny» / «пропуск» / «поправка». Песочница: временная папка."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "done-guard.py")
R, B, W = "mcp__plugin_mila-telegram_telegram__reply", "Bash", "Write"
ok = n = 0
tmp = tempfile.mkdtemp()


def use(mid, tid, name, **inp):
    return {"type": "assistant", "message": {"id": mid, "role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def res(tid, err=False):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": "x", "is_error": err}]}}


def journal(rows):
    p = os.path.join(tmp, "t%d.jsonl" % len(os.listdir(tmp)))
    with open(p, "w") as f:
        f.write('{"type":"queue-operation"}\nnot json\n')
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def run(inp):
    r = subprocess.run([sys.executable, G], input=json.dumps(inp) if not isinstance(inp, str) else inp, capture_output=True, text=True, timeout=20)
    if r.returncode:
        return "код %d" % r.returncode
    if not r.stdout.strip():
        return "пропуск"
    h = json.loads(r.stdout)["hookSpecificOutput"]
    return "deny" if h.get("permissionDecision") == "deny" else ("поправка" if "поправку" in h.get("additionalContext", "") else "?")


def chk(name, inp, want):
    global ok, n
    n += 1; got = run(inp); good = got == want; ok += good
    print(("✅ " if good else "❌ ") + name + ("" if good else "  (ждали %s, вышло %s)" % (want, got)))


def pre(rows, text, me="r1", **extra):
    return {"hook_event_name": "PreToolUse", "tool_name": R, "tool_use_id": me, "transcript_path": journal(rows), "tool_input": dict({"chat_id": "1", "text": text}, **extra)}


def prompt(text="сделай"):
    return {"type": "user", "message": {"role": "user", "content": text}}


def denied(tid):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": True,
            "content": "Не отправляю «сделано»: последний вызов этого хода вернулся с ошибкой."}]}}


def fail(rows, tid="b1", tool=B):
    return {"hook_event_name": "PostToolUseFailure", "tool_name": tool, "tool_use_id": tid, "transcript_path": journal(rows), "tool_input": {}, "error": "exit 2"}


# 1. команда и «сделала» в одном ответе, команда первой
same = [use("m1", "b1", B, command="deploy"), use("m1", "r1", R, chat_id="1", text="Сделала, выложено.")]
chk("«сделала» в одном ходу с командой без результата — стоп", pre(same, "Сделала, выложено."), "deny")
chk("✅ в одном ходу с командой — стоп", pre(same, "✅ страница на месте"), "deny")
chk("Write без результата в том же ходу — стоп", pre([use("m1", "w1", W), use("m1", "r1", R)], "Готово, файл записан"), "deny")
chk("MCP-инструмент работы в том же ходу — стоп", pre([use("m1", "x1", "mcp__srv__publish"), use("m1", "r1", R)], "Опубликовано и отправлено"), "deny")
# 2. то же, но без заявления — уходит
chk("«беру, вернусь с результатом» с командой — уходит", pre(same, "Беру, вернусь с результатом."), "пропуск")
chk("вопрос «готово?» — не заявление", pre(same, "Посмотрите, всё готово?"), "пропуск")
chk("«как будет готово» — план, не заявление", pre(same, "Пришлю, как будет готово."), "пропуск")
chk("«сделала» внутри слова-приставки не путает: «досделала» — пропуск", pre(same, "Досделала план, смотрю дальше"), "пропуск")
chk("«Готово ли? — да, вот вопрос» — вопрос, уходит", pre(same, "Готово ли? — да, вот вопрос"), "пропуск")
chk("«отправила вам файл» с files — вложение и есть результат, уходит", pre(same, "Отправила вам файл.", files=["/tmp/a.pdf"]), "пропуск")
chk("«отправила файл» без files при открытой команде — стоп", pre(same, "Отправила вам файл."), "deny")
chk("с files, но «выложено» при открытой команде — стоп", pre(same, "Выложено, файл прилагаю", files=["/tmp/a.pdf"]), "deny")
chk("«готово к вашей проверке» при открытой записи черновика — стоп (запись могла не пройти)", pre([use("m1", "w1", W), use("m1", "r1", R)], "Готово к вашей проверке"), "deny")
chk("«готово к вашей проверке» после записанного черновика — уходит", pre([use("m1", "w1", W), res("w1"), use("m2", "r1", R)], "Готово к вашей проверке"), "пропуск")
for ph in ("Ещё не готово — жду пробу", "Не отправила: бот не пишет первым", "Пока не исправлено", "⏳ ЖДЁМ РЕЗУЛЬТАТА · шаг 2 из 3 ✅ сборка"):
    chk("«%s» — не заявление, уходит" % ph, pre(same, ph), "пропуск")
chk("карточка ⏳ со строкой «✅ сборка» в начале строки — не заявление", pre(same, "⏳ ЖДЁМ РЕЗУЛЬТАТА\n✅ сборка\n▫️ тесты"), "пропуск")
chk("«Сделала: 12/12» — заявление, стоп", pre(same, "Сделала: 12/12"), "deny")
chk("«Пакет отправлен» (краткая форма) — заявление, стоп", pre(same, "Пакет отправлен"), "deny")
chk("✅ в середине строки без ⏳ — не заявление само по себе", pre(same, "Шаги: сборка ✅ тесты"), "пропуск")
chk("отрицание у одного слова не гасит другое: «не отправила, но сделала» — стоп", pre(same, "Не отправила, но сделала"), "deny")
# 3. результат уже был — уходит
chk("команда вернулась в прошлом ответе, «сделала» новым ответом — уходит",
    pre([use("m1", "b1", B), res("b1"), use("m2", "r1", R)], "Сделала, выложено."), "пропуск")
chk("рядом только чтение (Read, Grep) — уходит", pre([use("m1", "q1", "Read"), use("m1", "q2", "Grep"), use("m1", "r1", R)], "Готово"), "пропуск")
chk("рядом только реакция — уходит", pre([use("m1", "e1", "mcp__plugin_mila-telegram_telegram__react"), use("m1", "r1", R)], "Готово"), "пропуск")
chk("свой reply ещё не в журнале, прошлый ответ закрыт — уходит", pre([use("m0", "b0", B), res("b0")], "Сделала"), "пропуск")
chk("команда того же ответа уже вернулась — уходит", pre([use("m1", "b1", B), res("b1"), use("m1", "r1", R)], "Готово"), "пропуск")
# 3б. «сделала» после уже увиденной ошибки (случай старшей): команда упала прошлым ответом, ничего не прошло после
seen = [prompt(), use("m1", "b1", B), res("b1", True)]
chk("команда упала, «сделала» следующим ответом — стоп", pre(seen, "Сделала, выложено."), "deny")
chk("упала, но после неё рабочий вызов прошёл — уходит", pre(seen + [use("m2", "b2", B), res("b2")], "Сделала"), "пропуск")
chk("упала, после неё только чтение — всё ещё стоп", pre(seen + [use("m2", "q1", "Read"), res("q1")], "Готово"), "deny")
chk("упала, а ответ — факт без заявления — уходит", pre(seen, "Команда не прошла: нет файла. Чиню."), "пропуск")
chk("тот же текст второй раз после стопа — уходит (ошибка не про это дело)",
    pre(seen + [use("m2", "r0", R, chat_id="1", text="Готово"), denied("r0")], "Готово"), "пропуск")
chk("тот же текст уже уходил раньше (не стоп) — выхода нет, стоп",
    pre([prompt(), use("m0", "r0", R, chat_id="1", text="Готово"), res("r0"), use("m1", "b1", B), res("b1", True)], "Готово"), "deny")
chk("другой текст после стопа — снова стоп", pre(seen + [use("m2", "r0", R, chat_id="1", text="Готово"), denied("r0")], "Сделала!"), "deny")
chk("ошибка была в прошлом ходу человека — новый ход, уходит", pre(seen + [prompt("новое")], "Готово"), "пропуск")
# 4. обратный порядок: reply первым, команда упала после
rev = [use("m1", "r1", R, chat_id="1", text="Сделала, выложено."), res("r1"), use("m1", "b1", B)]
chk("«сделала» ушло, команда того же хода упала — поправка", fail(rev), "поправка")
chk("упала команда другого ответа — молчит", fail([use("m0", "b1", B), res("b1", True), use("m1", "r1", R, text="Сделала"), res("r1")]), "пропуск")
chk("reply был отклонён (ошибка) — не «ушло», молчит",
    fail([use("m1", "b1", B), use("m1", "r1", R, text="Сделала"), res("r1", True)]), "пропуск")
chk("reply ещё не ушёл — молчит", fail([use("m1", "b1", B), use("m1", "r1", R, text="Сделала")]), "пропуск")
chk("ушло без заявления — молчит", fail([use("m1", "r1", R, text="Беру"), res("r1"), use("m1", "b1", B)]), "пропуск")
chk("упало чтение (Read) — молчит", fail([use("m1", "r1", R, text="Готово"), res("r1"), use("m1", "q1", "Read")], "q1", "Read"), "пропуск")
# 5. fail open: сторож ошибок модели не держит сообщение на догадке
chk("нет журнала — уходит", {"hook_event_name": "PreToolUse", "tool_name": R, "tool_use_id": "r1", "transcript_path": "/nonexistent/t.jsonl", "tool_input": {"text": "Сделала"}}, "пропуск")
chk("вход не JSON — уходит", "{oops", "пропуск")
chk("другой инструмент — не мешает", {"hook_event_name": "PreToolUse", "tool_name": B, "transcript_path": journal(same), "tool_input": {"command": "ls"}}, "пропуск")
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
