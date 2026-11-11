#!/usr/bin/env python3
"""status.py — статус модулей ядра для их виджетов: Планировщик, Задачи, Библиотека, Сейф, Telegram.

Список закрытый. Каждая функция только читает дом и возвращает {"state": ok|attention|down|None, "numbers": [[значение, подпись]]}.
Один источник правды: считаю тем же кодом, что сам модуль (mila_cron.listing, cards.deck, library.verified_index, vault.has,
проверки doctor) — второго мнения не завожу. Никогда не отдаю: значения и имена ключей, тексты сообщений, имена людей, id чатов —
только числа, время и слово статуса. Сбой любого источника — «нет данных», а не старые цифры и не падение виджета.
«Жива ли служба Планировщика» из дома не видно (её состояние вне дома) — такого статуса здесь нет."""
import datetime as dt
import importlib.util
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", ".."))
WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")

L = lambda ru, en: {"ru": ru, "en": en}
CORE = {
    "planirovshchik": {"title": L("Планировщик", "Scheduler"), "actions": [{"label": L("Список", "List"), "mark": "list"}]},
    "zadachi": {"title": L("Задачи", "Tasks"), "actions": [{"label": L("Вопросы", "Questions"), "mark": "ask"}]},
    "biblioteka": {"title": L("Библиотека", "Library"), "actions": [{"label": L("Что есть", "What is there"), "mark": "list"}]},
    "sejf": {"title": L("Сейф", "Safe"), "actions": [{"label": L("Добавить ключ", "Add a key"), "mark": "add"}]},
    "telegram": {"title": L("Telegram", "Telegram"), "actions": [{"label": L("Проверить", "Check"), "mark": "check"}]},
}
# what Mila does on a press — her own core skills, nothing is run by the widget script
DO = {
    ("planirovshchik", "list"): "показать хозяину задачи расписания: python3 ~/.claude/skills/raspisanie/mila_cron.py list",
    ("zadachi", "ask"): "показать следующий вопрос карточкой: python3 ~/.claude/skills/cards/cards.py next inbox",
    ("biblioteka", "list"): "показать каталог паков: python3 ~/.claude/skills/library/library.py list",
    ("sejf", "add"): "спросить, какой ключ нужен, и выдать ссылку сейфа по навыку safe-link; ключ в чате не просить",
    ("telegram", "check"): "запустить доктора и сказать итог одной строкой: python3 ~/.claude/hooks/doctor.py",
}
STALE_DAYS = 7


def _mod(name, *paths):
    """A sibling core module by file path (the first that exists), under a private name."""
    for p in paths:
        if os.path.isfile(p):
            spec = importlib.util.spec_from_file_location("_vz_" + name, p)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            return m
    raise OSError("no module " + name)


def _when(t, now):
    """HH:MM for today, DD.MM HH:MM otherwise."""
    return t.strftime("%H:%M") if t.date() == now.date() else t.strftime("%d.%m %H:%M")


def planirovshchik():
    mc = _mod("mila_cron", os.path.join(SKILLS, "raspisanie", "mila_cron.py"))
    rows = mc.listing(); res = mc.results(); now = mc.now()
    on = [r for r in rows if r.get("enabled") and not r.get("expired")]
    nxt = sorted(dt.datetime.fromisoformat(r["next"]) for r in on if r.get("next"))
    def unfinished(r):
        if not r.get("last"): return False
        at = (res.get(r["id"]) or {}).get("at")
        try:      # the result is written to the minute: compare with the fire cut to the minute
            fired = dt.datetime.fromisoformat(str(r["last"]).replace("Z", "+00:00")).astimezone(now.tzinfo).replace(second=0, microsecond=0)
            return not at or dt.datetime.fromisoformat(at).astimezone(now.tzinfo) < fired
        except ValueError: return True
    loose = sum(1 for r in on if unfinished(r)); expired = sum(1 for r in rows if r.get("expired"))
    # there are jobs to fire, and the service has left no fresh pass mark for this home: nothing will fire — «down», not «works»
    cs = _mod("cronspec", os.path.join(SKILLS, "raspisanie", "cronspec.py"))
    beat = cs.last_beat(os.path.dirname(os.path.realpath(WORK)))
    alive = beat is not None and abs((now - beat).total_seconds()) <= cs.BEAT_FRESH
    return {"state": "down" if on and not alive else "attention" if loose or expired else "ok",
            "numbers": [[str(len(on)), L("задач", "jobs")], [_when(nxt[0], now) if nxt else "—", L("ближайшая", "next")], [str(loose), L("без итога", "no result")]]}


def zadachi():
    c = _mod("cards", os.path.join(SKILLS, "cards", "cards.py"))
    now = c.now(); inbox = c.deck("inbox"); prop = c.deck("proposals")
    hot = any(x.get("urgent") or ((c.parse(x.get("due")) or now) < now) for x in inbox)
    today = dt.datetime.now().astimezone().date().isoformat(); done = 0
    try:
        with open(os.path.join(WORK, "dela.jsonl"), encoding="utf-8") as f:
            for line in f:
                try: r = json.loads(line)
                except ValueError: continue
                if isinstance(r, dict) and r.get("дата") == today and r.get("ступень") == "сделала": done += 1
    except OSError:
        pass
    return {"state": "attention" if hot else "ok",
            "numbers": [[str(len(inbox)), L("ждёт вас", "wait for you")], [str(len(prop)), L("предложено", "proposed")], [str(done), L("сделано сегодня", "done today")]]}


def biblioteka():
    lib = _mod("library", os.path.join(SKILLS, "library", "library.py"))
    have = set()
    pdir = os.path.join(WORK, "packs")
    if os.path.isdir(pdir):
        have = {d for d in os.listdir(pdir) if os.path.isfile(os.path.join(pdir, d, "pack.json"))}
    cache = os.path.join(lib.CACHE, "library.json")
    if not os.path.isfile(cache):
        return {"state": None, "numbers": [[str(len(have)), L("паков стоит", "installed")], ["—", L("в каталоге", "in catalog")], ["—", L("новых", "new")]]}
    ix = lib.verified_index()
    if ix is None:      # the cached index is not the one this core release trusts
        return {"state": "down", "numbers": [[str(len(have)), L("паков стоит", "installed")], ["—", L("в каталоге", "in catalog")], ["—", L("новых", "new")]]}
    cat = [p["id"] for p in lib.packs(ix, "ru")]
    old = time.time() - os.path.getmtime(cache) > STALE_DAYS * 86400
    return {"state": "attention" if old else "ok",
            "numbers": [[str(len(have)), L("паков стоит", "installed")], [str(len(cat)), L("в каталоге", "in catalog")], [str(len([x for x in cat if x not in have])), L("новых", "new")]]}


def sejf():
    """Keys the installed packs name, as «have / missing» — only for the names the core can check without reading a value out."""
    v = _mod("vault", os.path.join(SKILLS, "safe-link", "scripts", "vault.py"))
    slot_of = {var: slot for slot, (var, _) in v.SLOTS.items()}
    names = set()
    pdir = os.path.join(WORK, "packs")
    for d in (os.listdir(pdir) if os.path.isdir(pdir) else []):
        try:
            with open(os.path.join(pdir, d, "pack.json"), encoding="utf-8") as f: m = json.load(f)
        except (OSError, ValueError):
            continue
        for k in (m.get("keys") or []) if isinstance(m, dict) else []:
            k = k.get("name") if isinstance(k, dict) else k
            if isinstance(k, str) and k in slot_of: names.add(k)
    have = sum(1 for k in names if v.has(slot_of[k])["has"])
    miss = len(names) - have
    return {"state": "attention" if miss else "ok", "numbers": [[str(have), L("ключей есть", "keys present")], [str(miss), L("не хватает", "missing")]]}


def telegram():
    d = _mod("doctor", os.path.join(SKILLS, "..", "hooks", "doctor.py"), os.path.join(SKILLS, "..", "install", "doctor.py"))
    rep = d.Report()
    for check in (d.check_daemon, d.check_journal, d.check_perms):     # the local checks only: no call to Telegram from a status
        check(rep)
    try:
        last = _when(dt.datetime.fromtimestamp(os.path.getmtime(d.EVENTS)).astimezone(), dt.datetime.now().astimezone())
    except OSError:
        last = "—"
    notes = len(rep.bad) + len(rep.warn)
    return {"state": "down" if rep.bad else "attention" if rep.warn else "ok",
            "numbers": [[last, L("последнее входящее", "last incoming")], [str(notes), L("замечаний", "notes")]]}


FUNCS = {"planirovshchik": planirovshchik, "zadachi": zadachi, "biblioteka": biblioteka, "sejf": sejf, "telegram": telegram}


def status(mid):
    """→ {"state", "numbers"}; anything went wrong — no data."""
    try:
        r = FUNCS[mid]()
        nums = [[str(a)[:24], b] for a, b in r.get("numbers", [])][:3]
        return {"state": r.get("state") if r.get("state") in ("ok", "attention", "down") else None, "numbers": nums}
    except Exception:
        return {"state": None, "numbers": []}
