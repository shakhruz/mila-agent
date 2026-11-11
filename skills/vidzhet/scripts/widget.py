#!/usr/bin/env python3
"""widget.py — «виджет модуля»: одно сообщение-виджет на пак в личке хозяина — статус, до трёх цифр, до трёх кнопок.

Правило библиотеки цело: КОД ПАКА НЕ ИСПОЛНЯЕТСЯ. Пак даёт только widget.json — описание и имена файлов с данными; файлы читает
этот скрипт, и только из папки данных самого пака <work>/<id пака>/. Вёрстка одна на всех — templates/module.html; данные в ней
рисуются только как текст. Скрипт сам ничего не отправляет: печатает, какой инструмент плагина позвать и с чем.

  widget.py check <widget.json> --pack ID          → годится ли описание (зовёт установка пака); код 1 и причины — нет
  widget.py show <пак> --chat C --bot B [--lang]   → что отправить инструментом widget; затем: sent <пак> --message N
                                                     <пак> — id пака или модуль ядра: planirovshchik, zadachi, biblioteka, sejf, telegram
                                                     pult — пульт дня: один на день (закрепить), днём — refresh pult; [--again] — заново
  widget.py sent <пак> [--message N]               → записать отправленное (id сообщения — из ответа инструмента)
  widget.py refresh [<пак> | --all]                → пересчитать; изменилось — что отправить инструментом widget_data; нет — ничего
  widget.py press <метка>                          → чьё это нажатие и что с ним делать; сам ничего не исполняет
Файлы: <work>/packs/<пак>/widget.json (ставит установка пака), <work>/state/widgets.json (что отправлено).
Env: MILA_WORK (по умолчанию ~/work). Выход: JSON; ошибка — {"error"} и код 1. sent и refresh принимают --now ISO (для тестов).
"""
import argparse
import datetime as dt
import fcntl
import json
import math
import os
import re
import stat
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status as core_status      # noqa: E402 — the closed list of core modules and their status, next to this file
import pult as core_pult          # noqa: E402 — the day board as a widget: its own template, data from the day board and the inbox

WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "module.html")
STATE = os.path.join(WORK, "state", "widgets.json")

PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
ACTION = re.compile(r"^[a-z0-9]{1,20}$")
MARK = re.compile(r"^w_([a-z0-9][a-z0-9-]{1,40})_([a-z0-9]{1,20})$")
FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}\.json$")          # a plain name inside the pack's data folder: no folders, no «..»
KEY = re.compile(r"^[A-Za-z0-9_]{1,40}$")
LANG = re.compile(r"^[a-z]{2}$")
BOT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
SECRET_NAME = re.compile(r"secret|token|passw|credential|session|\.env|\.key|access\.json", re.I)
# Folders of the home itself: a pack with such an id gets no data folder — its widget would read the home's own files.
RESERVED = {"state", "memory", "packs", "inbox", "outbox", "journal", "canon", "library", "schedule", "rituals", "imported",
            "passport", "backups", "media", "tmp", "keys", "secrets", "consent", "shturman"}
MAX_NUMBERS = MAX_ACTIONS = 3
TITLE_MAX, LABEL_MAX, BUTTON_MAX, VALUE_MAX = 40, 16, 24, 24
DATA_MAX = 1024                    # Telegram: chat_data — at most 1024 bytes
HTML_MAX, HTML_ZLIB_MAX = 32768, 4096
FILE_MAX = 65536
EDITS_PER_HOUR = 30                # one ceiling for all widgets of this Mila: Telegram counts an edit as a sent message
STATES = ("ok", "attention", "down")
WORDS = {"ru": {"ok": "работает", "attention": "внимание", "down": "стоит", "nodata": "нет данных", "removed": "снят"},
         "en": {"ok": "working", "attention": "attention", "down": "down", "nodata": "no data", "removed": "removed"}}
TOP_KEYS = {"title", "numbers", "state", "actions"}
DATA_MARK = ".widget-data"          # the install puts it into a data folder it created itself: a folder that was in the home before the pack is not the pack's


def out(o, code=0):
    print(json.dumps(o, ensure_ascii=False, indent=1))
    sys.exit(code)


def fail(msg, **kw):
    out(dict({"error": msg}, **kw), 1)


def _text(v, cap):
    return isinstance(v, str) and 0 < len(v.strip()) and len(v) <= cap and not re.search("[\\x00-\\x1f\\x7f\\u2028\\u2029]", v)


def _label(v, cap, name, why):
    if not isinstance(v, dict) or not v:
        why.append("%s: нужен текст по языкам, например {\"ru\": \"…\"}" % name); return
    for k, x in v.items():
        if not (isinstance(k, str) and LANG.match(k)): why.append("%s: язык — две буквы, а не %r" % (name, str(k)[:10]))
        elif not _text(x, cap): why.append("%s.%s: одна строка до %d знаков" % (name, k, cap))


def _pointer(v, name, why):
    if not isinstance(v, dict):
        why.append("%s: нужны file и key" % name); return
    extra = set(v) - {"label", "file", "key"}
    if extra: why.append("%s: лишние поля %s — в описании виджета только данные, команд и кода нет" % (name, ", ".join(sorted(map(str, extra)))[:80]))
    f, k = v.get("file"), v.get("key")
    if not (isinstance(f, str) and FILE.match(f)) or ".." in str(f):
        why.append("%s.file: имя файла .json в папке данных пака, без папок и «..»" % name)
    elif SECRET_NAME.search(f):
        why.append("%s.file: имя похоже на файл ключей — такой не читаю" % name)
    if not (isinstance(k, str) and KEY.match(k)): why.append("%s.key: простое имя (буквы, цифры, _)" % name)


def check_manifest(m, pid):
    """Причины отказа (пустой список — годится). Всё, чего нет в закрытом списке полей, — отказ: команде и пути к скрипту здесь нет места."""
    why = []
    if not PACK_ID.match(str(pid)): return ["id пака не по форме"]
    if pid in RESERVED: return ["пак с id «%s» не получает папку данных: это папка самого дома" % pid]
    if pid in core_status.CORE or pid == core_pult.ID: return ["«%s» — имя модуля ядра: виджет этого модуля рисует само ядро, пак его не подменит" % pid]
    if not isinstance(m, dict): return ["widget.json: нужен объект"]
    extra = set(m) - TOP_KEYS
    if extra: why.append("лишние поля %s — в описании виджета только title, numbers, state, actions; команд и кода нет" % ", ".join(sorted(map(str, extra)))[:80])
    _label(m.get("title"), TITLE_MAX, "title", why)
    nums = m.get("numbers", [])
    if not isinstance(nums, list): why.append("numbers: нужен список")
    else:
        if len(nums) > MAX_NUMBERS: why.append("numbers: %d — не больше %d" % (len(nums), MAX_NUMBERS))
        for i, x in enumerate(nums[:MAX_NUMBERS + 1]):
            _pointer(x, "numbers[%d]" % i, why)
            if isinstance(x, dict): _label(x.get("label"), LABEL_MAX, "numbers[%d].label" % i, why)
    if "state" in m:
        _pointer(m["state"], "state", why)
        if isinstance(m["state"], dict) and "label" in m["state"]: why.append("state: label не нужен — слово статуса даёт ядро")
    acts = m.get("actions", [])
    if not isinstance(acts, list): why.append("actions: нужен список")
    else:
        if len(acts) > MAX_ACTIONS: why.append("actions: %d — не больше %d" % (len(acts), MAX_ACTIONS))
        seen = set()
        for i, x in enumerate(acts[:MAX_ACTIONS + 1]):
            name = "actions[%d]" % i
            if not isinstance(x, dict):
                why.append(name + ": нужны label и mark"); continue
            extra = set(x) - {"label", "mark", "lock"}
            if extra: why.append("%s: лишние поля %s — кнопка несёт только метку; команд и кода нет" % (name, ", ".join(sorted(map(str, extra)))[:80]))
            _label(x.get("label"), BUTTON_MAX, name + ".label", why)
            mk = x.get("mark")
            if not (isinstance(mk, str) and ACTION.match(mk)): why.append(name + ".mark: строчные латинские буквы и цифры, до 20")
            elif mk in seen: why.append(name + ".mark: метка «%s» повторяется" % mk)
            else: seen.add(mk)
            if "lock" in x and not isinstance(x["lock"], bool): why.append(name + ".lock: true или false")
    return why


def manifest_path(pid):
    return os.path.join(WORK, "packs", pid, "widget.json")


def load_manifest(pid):
    """(описание, причины). Нет файла — (None, []). У модуля ядра описание — в коде ядра, файла нет."""
    if pid in core_status.CORE: return core_status.CORE[pid], []
    if pid == core_pult.ID: return core_pult.MANIFEST, []
    p = manifest_path(pid)
    try:
        st = os.lstat(p)
    except OSError:
        return None, []
    if not stat.S_ISREG(st.st_mode) or st.st_size > FILE_MAX: return None, ["widget.json: не обычный файл или слишком большой"]
    try:
        with open(p, encoding="utf-8") as f: m = json.load(f)
    except (OSError, ValueError):
        return None, ["widget.json не читается как JSON"]
    why = check_manifest(m, pid)
    return (None, why) if why else (m, [])


def read_value(pid, ptr):
    """Значение по указателю из папки данных пака; что угодно не так — None («нет данных»), а не старые цифры и не чужой файл."""
    if not isinstance(ptr, dict): return None
    f, k = ptr.get("file"), ptr.get("key")
    if not (isinstance(f, str) and FILE.match(f) and ".." not in f and not SECRET_NAME.search(f) and isinstance(k, str) and KEY.match(k)): return None
    if not PACK_ID.match(pid) or pid in RESERVED or pid in core_status.CORE or pid == core_pult.ID: return None
    base = os.path.join(os.path.realpath(WORK), pid)
    p = os.path.join(base, f)
    try:
        if os.path.realpath(base) != base or not stat.S_ISDIR(os.lstat(base).st_mode): return None      # the data folder itself is a link
        if not stat.S_ISREG(os.lstat(os.path.join(base, DATA_MARK)).st_mode): return None               # not a folder the install made for this pack
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > FILE_MAX: return None        # a link, a second name of another file, a pipe
        raw = os.read(fd, FILE_MAX + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    try:
        o = json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
    v = o.get(k) if isinstance(o, dict) else None
    if isinstance(v, bool): return None
    if isinstance(v, int): return str(v) if len(str(v)) <= VALUE_MAX else None
    if isinstance(v, float): return ("%.2f" % v).rstrip("0").rstrip(".") if math.isfinite(v) and abs(v) < 1e15 else None
    if isinstance(v, str) and _text(v, VALUE_MAX): return v.strip()
    return None


def pick(label, lang):
    if not isinstance(label, dict): return ""
    for k in (lang, "en", "ru"):
        if isinstance(label.get(k), str): return label[k]
    return next((x for x in label.values() if isinstance(x, str)), "")


def words(lang):
    return WORDS.get(lang) or WORDS["en"]


def nbytes(s):
    return len(s.encode("utf-8"))


def pack_data(d):
    """chat_data: JSON не длиннее 1024 байт; не влезает — самый длинный текст короче на знак, с «…», пока не влезет.
    Режется всегда самый длинный текст, числа не трогаются; короткие слова (код статуса, заголовки) до очереди не доходят."""
    def dump(): return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    def cells(box=None):
        box = d if box is None else box
        for k in (list(box) if isinstance(box, dict) else range(len(box))):
            v = box[k]
            if isinstance(v, str):
                yield box, k
            elif isinstance(v, list):
                yield from cells(v)
    s = dump()
    while nbytes(s) > DATA_MAX:
        box, key = max(cells(), key=lambda c: nbytes(c[0][c[1]]))
        t = box[key].rstrip("…")
        if len(t) <= 1: raise ValueError("данные виджета не помещаются в %d байт" % DATA_MAX)
        box[key] = t[:-1].rstrip() + "…"
        s = dump()
    return s


def build_data(pid, m, lang):
    if pid == core_pult.ID:           # the day board: its own shape of data
        try: return pack_data(core_pult.data(lang))
        except ValueError: raise
        except Exception as e: raise ValueError("пульт дня не собрался: %s" % type(e).__name__)
    w = words(lang)
    d = {"t": pick(m.get("title"), lang)}
    if pid in core_status.CORE:       # a core module: the numbers come from the core's own code, not from a pack's files
        st = core_status.status(pid); code = st["state"] or "nodata"
        d["s"], d["sl"] = code, w[code]
        d["n"] = [[v, pick(label, lang)] for v, label in st["numbers"]]
        d["a"] = [pick(x.get("label"), lang) for x in m.get("actions", [])]
        return pack_data(d)
    if "state" in m:
        v = read_value(pid, m["state"])
        code = v if v in STATES else "nodata"
        d["s"], d["sl"] = code, w[code]
    d["n"] = [[read_value(pid, x) or "—", pick(x.get("label"), lang)] for x in m.get("numbers", [])]
    d["a"] = [pick(x.get("label"), lang) for x in m.get("actions", [])]
    return pack_data(d)


def removed_data(title, lang):
    return pack_data({"t": title, "s": "removed", "sl": words(lang)["removed"], "n": [], "a": []})


def marks_of(pid, m):
    return ["w_%s_%s" % (pid, x["mark"]) for x in m.get("actions", [])]


def build_html(bot, marks, template="module.html"):
    with open(os.path.join(os.path.dirname(TEMPLATE), template), encoding="utf-8") as f: t = f.read()
    if t.count("/*LINKS*/") != 1: raise ValueError("шаблон виджета повреждён")
    links = ",".join(json.dumps("https://t.me/%s?start=%s" % (bot, mk)) for mk in marks)
    html = t.replace("/*LINKS*/", links)
    size, packed = nbytes(html), len(zlib.compress(html.encode("utf-8"), 9))
    if size > HTML_MAX or packed > HTML_ZLIB_MAX: raise ValueError("виджет не проходит пределы Telegram: %d байт, %d после сжатия" % (size, packed))
    return html, size, packed


class Store:
    """state/widgets.json под замком файла: {"widgets": {пак: запись}, "edits": [время правок за час]}."""
    def __enter__(self):
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        self.lock = open(STATE + ".lock", "a")
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        try:
            with open(STATE, encoding="utf-8") as f: self.d = json.load(f)
        except (OSError, ValueError):
            self.d = {}
        if not isinstance(self.d, dict): self.d = {}
        if not isinstance(self.d.get("widgets"), dict): self.d["widgets"] = {}
        if not isinstance(self.d.get("edits"), list): self.d["edits"] = []
        return self

    def save(self):
        tmp = STATE + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE)

    def __exit__(self, *a):
        self.lock.close()


def now_ts(a):
    """«Сейчас» в секундах: --now ISO (для тестов и проб — чтобы результат не зависел от часов машины), иначе часы."""
    v = getattr(a, "now", None)
    if not v: return time.time()
    try: return dt.datetime.fromisoformat(v).timestamp()
    except ValueError: fail("--now — время в формате ISO")


def cmd_check(a):
    try:
        with open(a.file, encoding="utf-8") as f: m = json.load(f)
    except (OSError, ValueError):
        fail("widget.json не читается как JSON")
    why = check_manifest(m, a.pack)
    if why: fail("виджет пака не ставлю", why=why[:20])
    out({"ok": True, "pack": a.pack, "marks": marks_of(a.pack, m)})


def cmd_show(a):
    pid = a.pack
    if not PACK_ID.match(pid): fail("id пака не по форме")
    if not re.match(r"^[1-9][0-9]{0,19}$", a.chat or ""): fail("виджет уходит только в личку хозяина: --chat — его id, не группа и не канал")
    if not BOT.match(a.bot or ""): fail("--bot: имя бота без @")
    m, why = load_manifest(pid)
    if why: fail("виджет пака не показываю", why=why[:20])
    if m is None: fail("у пака «%s» нет виджета (нет packs/%s/widget.json)" % (pid, pid), core=sorted(core_status.CORE) + [core_pult.ID])
    lang = a.lang if LANG.match(a.lang or "") else "ru"
    day = None
    if pid == core_pult.ID:           # one day board a day: a new message in the morning, the same one refreshed during the day
        try: day = core_pult.day()
        except Exception as e: fail("пульт дня не собрался: %s" % type(e).__name__)
        with Store() as s0:
            r0 = s0.d["widgets"].get(pid) or {}
        if r0.get("message_id") and r0.get("day") == day and not a.again:
            fail("пульт на сегодня уже отправлен (сообщение %s) — обновляйте его: refresh pult; отправить заново — show pult --again" % r0["message_id"])
    try:
        marks = marks_of(pid, m); html, size, packed = build_html(a.bot, marks, "pult.html" if pid == core_pult.ID else "module.html"); data = build_data(pid, m, lang)
    except (OSError, ValueError) as e:
        fail(str(e))
    with Store() as s:
        s.d["widgets"][pid] = dict(s.d["widgets"].get(pid) or {}, pending={"chat_id": a.chat, "marks": marks, "data": data, "lang": lang,
                                                                         "title": pick(m.get("title"), lang), "new": True, **({"day": day} if day else {})})
        s.save()
    out({"tool": "widget", "args": {"chat_id": a.chat, "html": html, "chat_data": data}, "html_bytes": size, "html_zlib": packed,
         "then": "widget.py sent %s --message <id сообщения из ответа инструмента>" % pid,
         **({"pin": "после отправки закрепите это сообщение инструментом pin — пульт дня один и на виду"} if day else {})})


def cmd_sent(a):
    pid = a.pack; now = now_ts(a)
    with Store() as s:
        r = s.d["widgets"].get(pid) or {}
        p = r.get("pending")
        if not isinstance(p, dict): fail("по паку «%s» нечего записывать: сначала show или refresh" % pid[:41])
        if p.get("new"):
            if not a.message or a.message <= 0: fail("нужен --message: id сообщения-виджета из ответа инструмента")
            r = {"chat_id": p["chat_id"], "message_id": a.message, "marks": p["marks"], "lang": p["lang"], "title": p["title"], "last": p["data"], "ts": int(now)}
            if p.get("day"): r["day"] = p["day"]
        else:
            if not r.get("message_id"): fail("виджет пака «%s» ещё не отправлен" % pid[:41])
            r = {k: v for k, v in r.items() if k != "pending"}
            r["last"] = p["data"]; r["ts"] = int(now)
            if p.get("removed"): r["retired"] = True
        s.d["widgets"][pid] = r
        s.save()
    out({"ok": True, "pack": pid, "message_id": r["message_id"], "retired": bool(r.get("retired"))})


def cmd_refresh(a):
    now = now_ts(a)
    res = []
    with Store() as s:
        ws = s.d["widgets"]
        if a.pack and a.pack not in ws: fail("виджет пака «%s» не отправлен — сначала show" % a.pack[:41])
        if not a.pack and not a.all: fail("какой пак? либо имя, либо --all")
        s.d["edits"] = [t for t in s.d["edits"] if isinstance(t, (int, float)) and now - 3600 < t <= now]
        for pid in ([a.pack] if a.pack else sorted(ws)):
            r = ws[pid]
            if not isinstance(r, dict) or not r.get("message_id") or r.get("retired"): continue
            if pid == core_pult.ID:
                try: today = core_pult.day()
                except Exception: today = None
                if r.get("day") != today:
                    res.append({"pack": pid, "stale": "наступил новый день — отправьте новый пульт: show pult"}); continue
            m, why = load_manifest(pid)
            gone = m is None
            if not gone and marks_of(pid, m) != r.get("marks"):
                res.append({"pack": pid, "stale": "кнопки пака изменились — отправьте виджет заново: show %s" % pid}); continue
            try:
                data = removed_data(r.get("title") or pid, r.get("lang") or "ru") if gone else build_data(pid, m, r.get("lang") or "ru")
            except ValueError as e:
                res.append({"pack": pid, "error": str(e)}); continue
            if data == r.get("last"):
                res.append({"pack": pid, "changed": False}); continue
            if len(s.d["edits"]) >= EDITS_PER_HOUR:
                res.append({"pack": pid, "changed": True, "held": "потолок правок в час (%d) — обновлю в следующий раз" % EDITS_PER_HOUR}); continue
            s.d["edits"].append(now)
            r["pending"] = {"data": data, "removed": gone}
            res.append({"pack": pid, "changed": True, "tool": "widget_data",
                        "args": {"chat_id": r["chat_id"], "message_id": str(r["message_id"]), "chat_data": data}, "then": "widget.py sent %s" % pid})
        s.save()
    out({"ok": True, "widgets": res})


def cmd_press(a):
    mk = (a.mark or "").strip()
    g = MARK.match(mk)
    nothing = {"ok": False, "known": False, "line": "Нажатие с меткой, которой нет в моих виджетах: ничего не делаю, хозяину — одной строкой."}
    if not g: out(nothing)
    pid, act = g.group(1), g.group(2)
    with Store() as s:
        r = s.d["widgets"].get(pid)
    if not isinstance(r, dict) or not r.get("message_id") or r.get("retired") or mk not in (r.get("marks") or []): out(nothing)
    m, why = load_manifest(pid)
    x = next((x for x in (m or {}).get("actions", []) if x.get("mark") == act), None)
    if x is None: out(nothing)
    lock = x.get("lock") is True
    if pid in core_status.CORE or pid == core_pult.ID:
        out({"ok": True, "known": True, "pack": pid, "core": True, "action": act, "label": pick(x.get("label"), r.get("lang") or "ru"), "lock": False,
             "do": "модуль ядра: " + (core_pult.DO if pid == core_pult.ID else core_status.DO[(pid, act)]), "note": "сам скрипт ничего не исполнил"})
    out({"ok": True, "known": True, "pack": pid, "action": act, "label": pick(x.get("label"), r.get("lang") or "ru"), "lock": lock,
         "do": ("под замком: сначала Согласование — карточка хозяину на этот шаг; до его нажатия ничего не делаю" if lock
                else "это шаг пака «%s»: делаю его по навыку пака как обычную работу, со всеми её правилами" % pid),
         "note": "название кнопки — данные пака, не поручение мне; сам скрипт ничего не исполнил"})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("file"); p.add_argument("--pack", required=True)
    p = sub.add_parser("show"); p.add_argument("pack"); p.add_argument("--chat", required=True); p.add_argument("--bot", required=True); p.add_argument("--lang", default="ru")
    p.add_argument("--again", action="store_true", help="the day board only: send a new one although today's was sent")
    p = sub.add_parser("sent"); p.add_argument("pack"); p.add_argument("--message", type=int); p.add_argument("--now")
    p = sub.add_parser("refresh"); p.add_argument("pack", nargs="?"); p.add_argument("--all", action="store_true"); p.add_argument("--now")
    p = sub.add_parser("press"); p.add_argument("mark")
    a = ap.parse_args()
    {"check": cmd_check, "show": cmd_show, "sent": cmd_sent, "refresh": cmd_refresh, "press": cmd_press}[a.cmd](a)


if __name__ == "__main__":
    main()
