#!/usr/bin/env python3
"""talents.py — after birth and the connectors I offer talents myself, one at a time, in the core's order (talents.json):
Shturman (a skill of the core), then packs of the checked library — business diagnostics, career direction, personal brand,
the book course. A pack this core's library does not hold is skipped for the owner and named in `list` («not in the library»).

  talents.py list [--lang ru]                      every talent: kind, state (offered | later | asked | active), and whether it is there
  talents.py next [--lang ru] [--now ISO]          the card to send now, or {"id": null, "why": …}
  talents.py answer <id> connect|later [--lang ru] the owner pressed: «later» is a full answer (not offered again by next);
                                                   Shturman «connect» opens ONLY the Shturman skill's own card with its three
                                                   risks and his «yes» there — nothing is connected here
  talents.py done <id>                             the talent stands (the pack is installed / Shturman is connected)

The measure of touches: next gives a card only when the previous talent card got an answer and a day has passed since it, and
never at night (22:00–08:00 in the owner's zone, USER.md «Часовой пояс — …», else Asia/Tashkent). A pack's card is the library's
own (library.py offer) — its text and buttons are not built here. Register: ~/work/talents/registry.json (600). Output: JSON."""
import argparse, datetime, importlib.util, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SKILLS = os.path.dirname(SKILL)
WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")
DIR = os.path.join(WORK, "talents")
REG = os.path.join(DIR, "registry.json")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
KINDS = ("skill", "pack")
SKILL_TALENTS = ("shturman",)        # the core's own skills that are talents; a pack is never named here
LANGS = ("ru", "en", "uz", "zh")
DAY = 24 * 3600
NIGHT = (22, 8)
WORDS = {
    "connect": {"ru": "Подключить", "en": "Connect", "uz": "Ulash", "zh": "连接"},
    "later": {"ru": "Позже", "en": "Later", "uz": "Keyinroq", "zh": "稍后"},
    "absent": {"ru": "нет в библиотеке", "en": "not in the library", "uz": "kutubxonada yo‘q", "zh": "库中没有"},
}


class Stop(Exception):
    pass


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False, indent=1)); sys.exit(code)


def tr(d, lang):
    return d.get(lang) or d.get("en") or next(iter(d.values()))


def order():
    try: d = json.load(open(os.path.join(SKILL, "talents.json"), encoding="utf-8"))
    except (OSError, ValueError): raise Stop("очередь талантов (talents.json) не читается")
    res = []
    for x in d.get("order") or []:
        tid, kind = str((x or {}).get("id") or ""), (x or {}).get("kind")
        if not ID.match(tid) or kind not in KINDS: raise Stop("talents.json: id или вид таланта в неверном виде")
        if kind == "skill" and tid not in SKILL_TALENTS: raise Stop("talents.json: навык %s — не талант ядра" % tid)
        res.append((tid, kind))
    return res


def registry():
    try:
        d = json.load(open(REG, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(reg):
    os.makedirs(DIR, mode=0o700, exist_ok=True); os.chmod(DIR, 0o700)
    tmp = REG + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, REG)


def py(script, *args):
    """a sibling skill's script → its JSON (or {} when it is missing or says nothing usable)."""
    p = os.path.join(SKILLS, script)
    if not os.path.isfile(p): return {}
    try:
        r = subprocess.run([sys.executable, "-B", p] + list(args), capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return json.loads(r.stdout or "{}")
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return {}


def library_ids(lang):
    cat = py("library/library.py", "list", "--lang", lang).get("catalog") or {}
    return {p.get("id") for ps in cat.values() if isinstance(ps, list) for p in ps if isinstance(p, dict)}


def installed():
    p = os.path.join(SKILLS, "mila-update", "update.py")
    try:
        spec = importlib.util.spec_from_file_location("mila_update_for_talents", p); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return set(m.installed_packs())
    except Exception:
        return set()


def shturman_on():
    return py("shturman/scripts/shturman.py", "status").get("connected") is True


def stands(tid, kind, packs):
    return shturman_on() if kind == "skill" else tid in packs


def owner_zone():
    sys.path.insert(0, os.path.join(SKILLS, "raspisanie"))
    try:
        import cronspec
        try: txt = open(os.path.join(WORK, "USER.md"), encoding="utf-8").read()
        except OSError: txt = ""
        return cronspec.owner_tz(txt)
    except Exception:
        import zoneinfo
        return zoneinfo.ZoneInfo("Asia/Tashkent")


def skill_card(tid, lang):
    d = json.load(open(os.path.join(SKILLS, tid, "talent.json"), encoding="utf-8"))
    ps = d["passport"]
    text = "\n".join([tr(d["offer"], lang), tr(ps["gives"], lang), tr(ps["needs"], lang), tr(ps["costs"], lang)])
    return {"text": text, "buttons": [[{"label": tr(WORDS["connect"], lang), "choice": "talent:%s:connect" % tid, "style": "success"},
                                       {"label": tr(WORDS["later"], lang), "choice": "talent:%s:later" % tid}]]}


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "next"):
        p = sub.add_parser(name); p.add_argument("--lang", default="ru"); p.add_argument("--now")
    p = sub.add_parser("answer"); p.add_argument("id"); p.add_argument("what", choices=("connect", "later")); p.add_argument("--lang", default="ru")
    p = sub.add_parser("done"); p.add_argument("id")
    a = ap.parse_args(argv)
    lang = getattr(a, "lang", "ru"); lang = lang if lang in LANGS else "en"
    try:
        q = order(); kinds = dict(q)
        if getattr(a, "id", None) is not None and (not ID.match(a.id) or a.id not in kinds): raise Stop("такого таланта в очереди ядра нет")
        reg = registry()
        if a.cmd == "list":
            lib, packs = library_ids(lang), installed()
            rows = []
            for tid, kind in q:
                there = True if kind == "skill" else tid in lib
                st = "active" if there and stands(tid, kind, packs) else (reg.get(tid) or {}).get("state", "offered")
                rows.append(dict({"id": tid, "kind": kind, "state": st}, **({} if there else {"note": tr(WORDS["absent"], lang)})))
            out({"talents": rows})
        if a.cmd == "answer":
            last = reg.get("_last") or {}
            if last.get("id") == a.id: last["answered"] = True; reg["_last"] = last
            if a.what == "later":
                reg[a.id] = {"state": "later", "ts": time.time()}; save(reg)
                out({"id": a.id, "state": "later", "note": "больше сам не предлагаю; попросит — покажу"})
            if kinds[a.id] == "skill":   # he is in the skill's own card now: not offered again by next, whatever he says there
                reg[a.id] = {"state": "asked", "ts": time.time()}
            save(reg)
            if kinds[a.id] == "skill":
                out({"id": a.id, "next": "открой карточку навыка %s — три строки риска и его «да» там; здесь ничего не подключено" % a.id})
            out({"id": a.id, "next": "кнопки пака — по карточке library.py offer %s (install-pack по нажатию)" % a.id})
        if a.cmd == "done":
            reg[a.id] = {"state": "active", "ts": time.time()}; save(reg); out({"id": a.id, "state": "active"})
        # next
        now = datetime.datetime.fromisoformat(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
        if now.tzinfo is None: now = now.replace(tzinfo=datetime.timezone.utc)
        h = now.astimezone(owner_zone()).hour
        if h >= NIGHT[0] or h < NIGHT[1]: out({"id": None, "why": "ночь у хозяина — карточек не шлю"})
        last = reg.get("_last") or {}
        if last and not last.get("answered"): out({"id": None, "why": "на прошлую карточку таланта (%s) ответа ещё нет" % last.get("id")})
        if last and now.timestamp() - float(last.get("ts") or 0) < DAY: out({"id": None, "why": "сегодня карточка таланта уже была — следующая через сутки"})
        lib, packs = None, installed()
        for tid, kind in q:
            if (reg.get(tid) or {}).get("state") in ("later", "active", "asked"): continue
            if kind == "pack":
                lib = library_ids(lang) if lib is None else lib
                if tid not in lib: continue
            if stands(tid, kind, packs): continue
            card = skill_card(tid, lang) if kind == "skill" else py("library/library.py", "offer", tid, "--lang", lang)
            if not card.get("text"): continue
            reg["_last"] = {"id": tid, "ts": now.timestamp(), "answered": False}; save(reg)
            out(dict({"id": tid, "kind": kind}, **card))
        out({"id": None, "why": "предлагать нечего: таланты очереди стоят, отложены или их нет в библиотеке"})
    except Stop as e:
        out({"ok": False, "why": str(e)}, 1)


if __name__ == "__main__":
    main()
