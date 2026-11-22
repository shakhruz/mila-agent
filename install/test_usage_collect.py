#!/usr/bin/env python3
"""usage_collect.py — расход по транскриптам Claude Code: один ответ модели считается один раз, сколькими бы строками он ни был
записан; нули наверху usage — числа берутся из iterations; служебные строки и чужие виды строк не считаются; день — по часам
хозяина, не по UTC; незнакомая модель — токены есть, денег нет; свой prices.json перекрывает встроенный; журнал дописывается.
Строки транскрипта собраны по форме живого файла (Claude Code в доме Разработки, 17.11.2026: имена полей строки assistant,
usage и служебных видов строк; значения выдуманы). Всё во временной папке (CLAUDE_CONFIG_DIR).
Usage: python3 test_usage_collect.py [папка с usage_collect.py]"""
import json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); K = os.path.join(D, "usage_collect.py")
ok = n = 0
def chk(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:400]))

TZ = timezone(timedelta(hours=5))                      # пояс хозяина в тесте: Ташкент
today = datetime.now(TZ).replace(hour=12, minute=0, second=0, microsecond=0)
def z(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

def usage(i=0, o=0, cw=0, cr=0, think=0, iterations=None):
    """блок usage как в живом транскрипте: рядом с четырьмя счётчиками лежат поля, которые счёту не нужны"""
    return {"input_tokens": i, "output_tokens": o, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
            "cache_creation": {"ephemeral_1h_input_tokens": cw, "ephemeral_5m_input_tokens": 0}, "fallback_credit": None,
            "inference_geo": "not_available", "iterations": iterations or [], "output_tokens_details": {"thinking_tokens": think},
            "server_tool_use": {"web_fetch_requests": 0, "web_search_requests": 0}, "service_tier": "standard", "speed": "standard"}

def line(kind, when, rid, mid, model, u, block):
    """строка assistant: один ответ модели пишется несколькими такими строками, usage в них повторяется"""
    return {"type": "assistant", "timestamp": z(when), "requestId": rid, "requestRef": rid, "uuid": "u-%s-%s" % (mid, kind), "parentUuid": "p",
            "sessionId": "s-1", "isSidechain": False, "cwd": "/home/x/work", "entrypoint": "cli", "gitBranch": "main", "userType": "external",
            "version": "9.9.9", "apiBlockIndex": 0, "effort": "medium", "perTurnEffort": "medium", "requestedModel": model,
            "message": {"id": mid, "type": "message", "role": "assistant", "model": model, "content": [block], "stop_reason": "tool_use",
                        "stop_sequence": None, "stop_details": None, "container": None, "context_management": None, "diagnostics": None,
                        "input_transformations": [], "usage": u}}

FABLE, OPUS, HAIKU55, NEW = "claude-fable-5-2", "claude-opus-5-5", "claude-haiku-5-5", "claude-nova-1"
u1 = usage(100, 1000, 2000, 30000, think=400)
u2 = usage(0, 0, 0, 0, iterations=[{"input_tokens": 10, "output_tokens": 200, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5000},
                                   {"input_tokens": 5, "output_tokens": 300, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000}, "мусор"])
rows = [
    {"type": "session-owner", "sessionId": "s-1", "accountUuid": "a", "organizationUuid": "o"},
    {"type": "user", "timestamp": z(today), "sessionId": "s-1", "uuid": "u0", "message": {"role": "user", "content": "привет", "usage": usage(9, 9, 9, 9)}},
    line("thinking", today, "req-1", "msg-1", FABLE, u1, {"type": "thinking", "thinking": "…"}),      # один ответ — три строки
    line("text", today, "req-1", "msg-1", FABLE, u1, {"type": "text", "text": "…"}),
    line("tool", today, "req-1", "msg-1", FABLE, u1, {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}),
    {"type": "system", "subtype": "hook", "timestamp": z(today), "sessionId": "s-1", "hookCount": 1},
    {"type": "api-request", "id": "x", "timestamp": z(today), "sessionId": "s-1", "params": {"usage": usage(7, 7, 7, 7)}},
    line("text", today, "req-2", "msg-2", OPUS, u2, {"type": "text", "text": "…"}),                   # нули наверху, числа в iterations
    line("text", today, "req-3", "msg-3", "<synthetic>", usage(1, 1, 1, 1), {"type": "text", "text": "…"}),   # служебное сообщение оболочки
    line("text", today, "req-4", "msg-4", HAIKU55, usage(1000, 2000, 0, 0), {"type": "text", "text": "…"}),
    line("text", today - timedelta(days=10), "req-5", "msg-5", FABLE, usage(5, 5, 5, 5), {"type": "text", "text": "…"}),   # старше периода
    line("text", today.replace(hour=1, minute=30), "req-6", "msg-6", FABLE, usage(1, 2, 3, 4), {"type": "text", "text": "…"}),   # 01:30 по Ташкенту = вчера по UTC
    dict(line("text", today, "", "", FABLE, usage(1, 1, 0, 0), {"type": "text", "text": "…"}), requestId="", message=dict(line("x", today, "", "", FABLE, usage(1, 1, 0, 0), {})["message"], id="")),
    dict(line("text", today, "req-7", "msg-7", FABLE, None, {"type": "text", "text": "…"})),            # usage не объект
]
C = tempfile.mkdtemp(prefix="usage-"); P = os.path.join(C, "projects", "-home-x-work"); os.makedirs(P)
with open(os.path.join(P, "s-1.jsonl"), "w", encoding="utf-8") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.write('{"type": "assistant", "timestamp": "' + z(today) + '", "message": {"usage": {"input_tokens": 99999')     # недописанная последняя строка
open(os.path.join(P, "zametki.txt"), "w").write("не транскрипт")

def run(*a, env=None):
    e = dict(os.environ, CLAUDE_CONFIG_DIR=C, TZ="Asia/Tashkent"); e.update(env or {})
    p = subprocess.run([sys.executable, K, *a], env=e, capture_output=True, text=True, timeout=60); return p.returncode, p.stdout, p.stderr
def day_of(out, d):
    j = json.loads(out); days = j["days"] if isinstance(j, dict) else j
    return next((x for x in days if x["day"] == d), None)

code, out, err = run("--json", "--no-write")
T = today.strftime("%Y-%m-%d"); d = day_of(out, T) if code == 0 else None
chk("запуск на транскрипте живой формы: код 0, есть сегодняшний день", code == 0 and d is not None, (code, out[:300], err[:300]))
M = {m["model"]: m for m in (d or {}).get("models", [])}
chk("один ответ, записанный тремя строками, посчитан ОДИН раз (не 3×): вход 100, выход 1000, запись кэша 2000, чтение 30000, размышление 400",
    M.get(FABLE, {}).get("in") == 100 + 1 + 1 and M[FABLE]["out"] == 1000 + 2 + 1 and M[FABLE]["cache_write"] == 2000 + 3 and M[FABLE]["cache_read"] == 30000 + 4
    and M[FABLE]["thinking"] == 400 and M[FABLE]["turns"] == 3, M.get(FABLE))
chk("нули наверху usage — числа взяты из iterations (сумма двух, мусор в списке не мешает): 15 / 500 / 100 / 6000",
    (M.get(OPUS, {}).get("in"), M[OPUS]["out"], M[OPUS]["cache_write"], M[OPUS]["cache_read"], M[OPUS]["turns"]) == (15, 500, 100, 6000, 1), M.get(OPUS))
chk("не считаются: строки user, system, api-request, служебная модель <synthetic>, недописанная строка, usage не объектом, чужой файл",
    set(M) == {FABLE, OPUS, HAIKU55} and (d["total"]["in"], d["total"]["turns"]) == (102 + 15 + 1000, 3 + 1 + 1), (sorted(M), d["total"]))
chk("строка без requestId и без id ответа не теряется — считается как есть (потерять расход хуже)", M[FABLE]["turns"] == 3)
chk("день — по часам хозяина: ответ в 01:30 по Ташкенту (вчера по UTC) попал в сегодня; ответ 10-дневной давности — нет",
    M[FABLE]["cache_read"] == 30004 and day_of(out, (today - timedelta(days=10)).strftime("%Y-%m-%d")) is None)
chk("цена семейства: fable-5-2 считается по claude-fable-5, opus-5-5 — по claude-opus-5; сумма ответа fable = вход+выход+запись+чтение кэша по прайсу",
    M[FABLE]["priced_as"] == "claude-fable-5" and M[OPUS]["priced_as"] == "claude-opus-5"
    and abs(M[FABLE]["cost_usd"] - (102 * 3.0 + 1003 * 15.0 + 2003 * 3.75 + 30004 * 0.30) / 1e6) < 1e-9, M[FABLE])
chk("модель, которой нет в прайсе (claude-haiku-5-5: в таблице только haiku-4-5), — токены есть, денег нет, день помечен «цена неполная»",
    M[HAIKU55]["cost_usd"] is None and M[HAIKU55]["priced_as"] is None and M[HAIKU55]["out"] == 2000 and d["cost_usd"] is None and d["cost_complete"] is False, (M[HAIKU55], d["cost_usd"]))

json.dump({"_basis": "svoj-prajs", HAIKU55: {"in": 1.0, "out": 5.0, "cache_write": 1.25, "cache_read": 0.10}}, open(os.path.join(C, "prices.json"), "w"))
code, out, err = run("--json", "--no-write"); d = day_of(out, T); M = {m["model"]: m for m in d["models"]}
chk("свой prices.json перекрывает встроенный: haiku-5-5 получил цену, день стал полным, сумма дня = сумма моделей",
    abs(M[HAIKU55]["cost_usd"] - (1000 * 1.0 + 2000 * 5.0) / 1e6) < 1e-9 and d["cost_complete"] is True
    and abs(d["cost_usd"] - round(sum(m["cost_usd"] for m in d["models"]), 4)) < 1e-9, (M[HAIKU55], d["cost_usd"]))
open(os.path.join(C, "prices.json"), "w").write("{битый")
code, out, err = run("--json", "--no-write")
chk("битый prices.json — не падение: считаю по встроенным ценам и говорю об этом", code == 0 and "prices.json" in err and day_of(out, T) is not None)
os.remove(os.path.join(C, "prices.json"))

log = os.path.join(C, "usage-log.jsonl")
chk("--no-write журнал не трогает", not os.path.exists(log))
run("--json")
chk("--json — только вывод: журнал не пишется (так устроено сегодня; журнал ведёт обычный запуск)", not os.path.exists(log))
code, out, err = run(); a = os.path.getsize(log) if os.path.exists(log) else 0
chk("обычный запуск: сводка называет модель без цены и не выдаёт сумму дня за точную", code == 0 and "цены неизвестны для: claude-haiku-5-5" in out and "$?" in out, out[-400:])
code, out, err = run(); b = os.path.getsize(log) if os.path.exists(log) else 0
L = [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()] if os.path.exists(log) else []
chk("журнал usage-log.jsonl дописывается (растёт, не переписывается), строки помечены counting=per-response, файл 600", a > 0 and b == 2 * a
    and all(r.get("counting") == "per-response" and r.get("basis") for r in L) and oct(os.stat(log).st_mode)[-3:] == "600", (a, b))
code, out, err = run("--json", "--no-write", "--days", "30")
chk("--days 30: десятидневный ответ появляется своим днём", code == 0 and day_of(out, (today - timedelta(days=10)).strftime("%Y-%m-%d")) is not None)
E = tempfile.mkdtemp(prefix="usage-empty-")
p = subprocess.run([sys.executable, K, "--json", "--no-write"], env=dict(os.environ, CLAUDE_CONFIG_DIR=E), capture_output=True, text=True)
chk("нет папки проектов — код 1 и понятная строка, не падение", p.returncode == 1 and "нет каталога проектов" in p.stderr and "Traceback" not in p.stderr)
shutil.rmtree(C, ignore_errors=True); shutil.rmtree(E, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
