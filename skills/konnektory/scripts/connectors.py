#!/usr/bin/env python3
"""connectors.py — Mila's connectors: talents that give her a new sense through an outside service (hearing, imagination, a voice).
A built-in connector lies in the core (skills/<id>/connector.json — data only) and is ACTIVATED, not downloaded. This script keeps
the register of the home and builds every text; it runs no code of a connector and never prints a key.

  connectors.py list [--lang ru]            the register: every built-in connector and its state — offered | later | active | off
  connectors.py next [--lang ru]            which connector to offer now (the order of birth; «later» and «off» are not offered again)
  connectors.py offer <id> [--lang ru]      the card: one line «what it gives you» and two buttons — «Activate …» / «Later»
  connectors.py later <id>                  the owner said «later»: not offered again by `next`; `offer` at his own request still works
  connectors.py steps <id> [--lang ru]      three steps where to get the key, and which safe record to ask for (the key goes past the chat)
  connectors.py check <id>                  the key is in the safe and the service accepts it → state «active»; otherwise the reason
  connectors.py trial <id> [--lang ru]      the trial line after activation (a paid trial names its price and waits for «yes»)
  connectors.py off <id> [--lang ru]        switch the connector off at once; the key stays in the safe
  connectors.py on <id>                     switch it back on (the key is checked again)
State: ~/work/connectors/registry.json (600) and a flag file ~/work/connectors/<id>.off that the procedure itself respects.
Which service a connector talks to and how its key is checked is a closed list HERE (SERVICES): a connector.json cannot name an
address — otherwise a file of data could send the owner's key anywhere. Output: JSON."""
import argparse, json, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", ".."))
WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")
DIR = os.path.join(WORK, "connectors")
REG = os.path.join(DIR, "registry.json")
ORDER = ("sluh",)                                   # the order of birth; a connector not named here is not built-in
SERVICES = {                                        # the closed list: where a key is checked and how it is sent
    "deepgram": {"url": "https://api.deepgram.com/v1/projects", "header": "Authorization", "prefix": "Token "},
}
STATES = ("offered", "later", "active", "off")
LANGS = ("ru", "en", "uz", "zh")
WORDS = {
    "activate": {"ru": "Активировать %s", "en": "Activate %s", "uz": "%sni faollashtirish", "zh": "激活%s"},
    "later": {"ru": "Позже", "en": "Later", "uz": "Keyinroq", "zh": "稍后"},
    "state": {"offered": {"ru": "предложен", "en": "offered", "uz": "taklif qilingan", "zh": "已提议"},
              "later": {"ru": "отложен", "en": "later", "uz": "keyinga qoldirilgan", "zh": "稍后"},
              "active": {"ru": "активирован", "en": "active", "uz": "faol", "zh": "已激活"},
              "off": {"ru": "выключен", "en": "off", "uz": "o‘chirilgan", "zh": "已关闭"}},
}


class Stop(Exception):
    pass


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False, indent=1)); sys.exit(code)


def tr(d, lang):
    return d.get(lang) or d.get("en") or next(iter(d.values()))


def clean(s, n=400):
    """A text of a connector is data shown to a person: one line, no control characters, no links but plain names."""
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", str(s))).strip()[:n]


def load(cid):
    if cid not in ORDER: raise Stop("нет такого встроенного коннектора: %s (есть: %s)" % (str(cid)[:30], ", ".join(ORDER)))
    p = os.path.join(SKILLS, cid, "connector.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        raise Stop("паспорт коннектора %s не читается" % cid)
    if d.get("id") != cid or d.get("service") not in SERVICES: raise Stop("паспорт коннектора %s: не тот id или сервис не из списка ядра" % cid)
    safe = d.get("safe") or {}
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", str(safe.get("name") or "")) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,40}", str(safe.get("field") or "")):
        raise Stop("паспорт коннектора %s: запись сейфа названа неверно" % cid)
    for k in ("sense", "offer", "trial", "removal"):
        if not isinstance(d.get(k), dict): raise Stop("паспорт коннектора %s: нет части «%s»" % (cid, k))
    ps = d.get("passport") or {}
    if not all(isinstance(ps.get(k), dict) for k in ("gives", "needs", "costs")): raise Stop("паспорт коннектора %s: нужны «что даёт», «что нужно», «сколько стоит»" % cid)
    if not isinstance(d.get("steps"), dict) or not all(isinstance(v, list) and 1 <= len(v) <= 3 for v in d["steps"].values()): raise Stop("паспорт коннектора %s: шагов — от одного до трёх" % cid)
    return d


def registry():
    try:
        d = json.load(open(REG, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(reg):
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    tmp = REG + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, REG)


def set_state(cid, state, **extra):
    reg = registry(); rec = dict(reg.get(cid) or {}); rec.update(state=state, ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"), **extra)
    reg[cid] = rec; save(reg)
    flag = os.path.join(DIR, cid + ".off")
    if state == "off": open(flag, "w").close()
    else:
        try: os.remove(flag)
        except OSError: pass
    return rec


def state_of(cid):
    s = (registry().get(cid) or {}).get("state")
    return s if s in STATES else "offered"


def read_key(d):
    """The key from the safe, for the check only. → (key or None, why). Never printed."""
    sys.path.insert(0, os.path.join(SKILLS, "safe-link", "scripts"))
    try:
        import safe_read
    except ImportError:
        return None, "навыка сейфа (safe-link) в доме нет"
    try:
        v = safe_read.read_safe(d["safe"]["name"]).get(d["safe"]["field"], "")
    except safe_read.SafeError as e:
        return None, str(e)[:160]
    v = (v or "").strip()
    return (v, "") if v else (None, "в сейфе нет поля %s" % d["safe"]["field"])


def http_status(url, headers, timeout=20):
    """One door to the network (replaced in the test). → HTTP status, or 0 when there is no answer."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError, ValueError):
        return 0


def check_key(d):
    """→ (ok, reason). The key goes only to the address of the closed list."""
    key, why = read_key(d)
    if not key: return False, why
    s = SERVICES[d["service"]]
    code = http_status(s["url"], {s["header"]: s["prefix"] + key})
    if code == 200: return True, ""
    if code in (401, 403): return False, "сервис не принял ключ (HTTP %d) — нужен новый ключ" % code
    if code == 0: return False, "сервис не ответил — проверю ещё раз позже, ключ в сейфе"
    return False, "сервис ответил HTTP %d — проверю ещё раз позже" % code


def card(d, lang):
    sense = clean(tr(d["sense"], lang), 40)
    return {"text": clean(tr(d["offer"], lang)) + "\n" + clean(tr(d["passport"]["needs"], lang)) + "\n" + clean(tr(d["passport"]["costs"], lang)),
            "buttons": [[{"label": tr(WORDS["activate"], lang) % sense, "choice": "connector:%s:activate" % d["id"], "style": "success"},
                         {"label": tr(WORDS["later"], lang), "choice": "connector:%s:later" % d["id"]}]]}


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "next"):
        p = sub.add_parser(name); p.add_argument("--lang", default="ru")
    for name in ("offer", "steps", "trial", "off"):
        p = sub.add_parser(name); p.add_argument("id"); p.add_argument("--lang", default="ru")
    for name in ("later", "check", "on"):
        p = sub.add_parser(name); p.add_argument("id")
    a = ap.parse_args(argv)
    lang = getattr(a, "lang", "ru"); lang = lang if lang in LANGS else "en"
    try:
        if a.cmd == "list":
            rows = []
            for cid in ORDER:
                d = load(cid); st = state_of(cid)
                rows.append({"id": cid, "sense": clean(tr(d["sense"], lang), 40), "state": st, "state_word": tr(WORDS["state"][st], lang), "gives": clean(tr(d["passport"]["gives"], lang))})
            out({"connectors": rows})
        if a.cmd == "next":
            for cid in ORDER:
                if state_of(cid) == "offered":
                    d = load(cid); out(dict({"id": cid}, **card(d, lang)))
            out({"id": None, "note": "предлагать нечего: все встроенные коннекторы активированы, отложены или выключены"})
        d = load(a.id)
        if a.cmd == "offer":
            if state_of(a.id) == "active": out({"id": a.id, "state": "active", "note": "уже активирован"})
            out(dict({"id": a.id}, **card(d, lang)))
        if a.cmd == "later":
            if state_of(a.id) == "active": out({"id": a.id, "state": "active", "note": "уже активирован — «позже» не пишу"})
            out({"id": a.id, "state": set_state(a.id, "later")["state"], "note": "больше не предлагаю сама; хозяин попросит — offer"})
        if a.cmd == "steps":
            out({"id": a.id, "steps": [clean(x) for x in tr(d["steps"], lang)], "safe": {"name": d["safe"]["name"], "fields": [d["safe"]["field"]]},
                 "how": "ключ — только ссылкой сейфа (навык safe-link), с этими именем и полем; в чат ключ не прошу и не принимаю. Когда сейф скажет «сохранено» — connectors.py check %s" % a.id})
        if a.cmd in ("check", "on"):
            ok, why = check_key(d)
            if not ok: out({"id": a.id, "ok": False, "state": state_of(a.id), "why": why}, 1)
            out({"id": a.id, "ok": True, "state": set_state(a.id, "active")["state"]})
        if a.cmd == "trial":
            if state_of(a.id) != "active": out({"id": a.id, "ok": False, "why": "коннектор не активирован — пробы нет"}, 1)
            res = {"id": a.id, "ok": True, "text": clean(tr(d["trial"], lang)), "paid": bool(d.get("paid_trial"))}
            if res["paid"]: res["note"] = "проба платная: сначала цена и «да» хозяина"
            out(res)
        if a.cmd == "off":
            out({"id": a.id, "state": set_state(a.id, "off")["state"], "text": clean(tr(d["removal"], lang))})
    except Stop as e:
        out({"ok": False, "why": str(e)}, 1)


if __name__ == "__main__":
    main()
