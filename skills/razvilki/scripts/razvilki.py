#!/usr/bin/env python3
"""Журнал развилок Милы: иду по рекомендуемому пути, не дожидаясь, и записываю точку — что выбрала, почему и что придётся
переделать, если хозяин позже выберет другое. Файл work/razvilki.jsonl в доме Милы (600), только дописывается, номер и запись — под одним замком.
  razvilki.py add --vopros <≤160> --varianty "А: …|Б: …[|В: …]" --vybrala Б --pochemu <≤160> --peredelat <что переделывать при смене, ≤200> --ulika <указатель>   → R-0001
  razvilki.py switch R-0001 --na А --ulika <сообщение хозяина: msg:…>     → курс сменён; печатает, что переделать
  razvilki.py done R-0001 --prichina <≤120>                           → точка больше не меняется (принято, срок прошёл, дальше необратимо)
  razvilki.py list [--open] · itog [--days 7] [--json]
Развилка — только для своей обратимой работы Милы. Под замком развилок нет: деньги, слово от имени хозяина, отправка, публикация,
удаление — это Согласование (карточка, его нажатие), а не «иду по Б». Скрипт отказывает, если в вопросе, вариантах или «переделать»
слова замка; если слово значит другое («перевод текста»), это говорится прямо: --ne-zamok "<почему>" — и остаётся в журнале.
Улика — указатель (правила dela.py). В текстах — роль, не имя. Only stdlib."""
import argparse, datetime as dt, fcntl, importlib.util, json, os, re, sys

H = os.path.dirname(os.path.abspath(__file__))
HOME_WORK = os.path.expanduser(os.environ.get("MILA_WORK", "~/work"))
LOG = os.path.join(HOME_WORK, "razvilki.jsonl")
NUM = re.compile(r"^R-\d{4,6}$")
LETTERS = "АБВГ"
# words of a lock: money, the owner's name, sending out, publishing, deleting, signing — never a fork
ZAMOK = re.compile(r"(?i)(?<![а-яёa-z])(?:оплат|оплач|плат[её]ж|купи|куплю|покуп|закаж|заказать|деньг|перевод|перевед|перевест|счёт|счет[а-я]*\b|"
                   r"отправ|разосл|рассыл|пересл|перешл|опублик|публикац|выложи|запост|удал|сотри\b|сотру\b|стер[её]т|от имени|подпиш|подписа|"
                   r"от (?:вашего|его|её|моего|своего) лица|за вас\b|"
                   r"(?:напис|напиш|ответ[ьи]|отвеч)[а-яё]*\s+(?:\S+\s+)?(?:клиент|партн[её]р|гост|заказчик|поставщик|подписчик)|forward|"
                   r"pay\b|payment|purchase|buy\b|transfer|send|publish|post it|delete|remove|sign\b|signed|signing)")


# a word that mixes Latin and Cyrillic letters («Oплатить» with a Latin O) hides from the list above — refused as it is
MIXED = re.compile(r"(?i)[a-z][a-z0-9]*[а-яё]|[а-яё][а-яё0-9]*[a-z]")


def _dela():
    p = os.path.join(os.path.dirname(os.path.dirname(H)), "dela", "scripts", "dela.py")
    try:
        spec = importlib.util.spec_from_file_location("mila_dela", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    except Exception:
        sys.exit("нет навыка dela рядом — улику и личные данные проверить нечем, не пишу")
    return m


def now(a):
    if getattr(a, "now", None):
        try: t = dt.datetime.fromisoformat(a.now)
        except ValueError: sys.exit("--now — время в формате ISO")
        return t if t.tzinfo else t.astimezone()
    return dt.datetime.now().astimezone()


def when(r):
    try: t = dt.datetime.fromisoformat(str(r.get("ts") or ""))
    except ValueError: return None
    return t if t.tzinfo else t.astimezone()


def rows(f):
    f.seek(0); res = []
    for l in f.read().splitlines():
        try: r = json.loads(l)
        except ValueError: continue
        if isinstance(r, dict) and NUM.match(str(r.get("n") or "")) and when(r) is not None: res.append(r)
    return res


def state(rs):
    st = {}
    for r in rs:
        n, s = r["n"], r.get("шаг"); p = st.get(n)
        if s == "точка" and p is None and isinstance(r.get("варианты"), dict) and r.get("выбрано") in r["варианты"]:
            st[n] = {"n": n, "вопрос": r.get("вопрос"), "варианты": r["варианты"], "выбрано": r["выбрано"], "переделать": r.get("переделать"),
                     "открыта": True, "смен": 0, "ts": when(r), "закрыта_ts": None}
        elif p is None: continue
        elif s == "смена" and p["открыта"] and r.get("на") in p["варианты"]: p["выбрано"] = r["на"]; p["смен"] += 1
        elif s == "закрыта" and p["открыта"]: p["открыта"] = False; p["закрыта_ts"] = when(r)
    return st


def text_ok(D, name, v, cap, need=True):
    v = (v or "").strip()
    if not v:
        if need: sys.exit("«%s» — пусто" % name)
        return v
    if len(v) > cap: sys.exit("«%s» — коротко, до %d знаков" % (name, cap))
    if "\n" in v or "\r" in v: sys.exit("«%s» — одной строкой" % name)
    if D.pd_hit(v): sys.exit("в поле «%s» личные данные — роль вместо имени, без номеров и адресов" % name)
    return v


def ulika(D, u, kinds=None):
    u = (u or "").strip()
    if not u or not D.ULIKA.match(u): sys.exit("нет улики — не пишу (msg:… | file:… | link:… | journal:… | commit:…)")
    if kinds and u.split(":", 1)[0] not in kinds: sys.exit("улика этой ступени — %s" % " или ".join(k + ":" for k in kinds))
    if not D.ulika_ok(u): sys.exit("улика не сходится: файл — внутри work и существует; commit — хэш; msg — <чат>:<номер>; link — https")
    return u


def locked(fn):
    os.makedirs(HOME_WORK, exist_ok=True)
    fd = os.open(LOG, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            rs = rows(f); out, msg, err = fn(rs, state(rs))
            for row in out: f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    if err: sys.exit(err)
    print(msg)


def variants(D, raw):
    parts = [x.strip() for x in (raw or "").split("|") if x.strip()]
    if not 2 <= len(parts) <= 4: sys.exit("варианты — от двух до четырёх: \"А: …|Б: …|В: …\"")
    out = {}
    for i, x in enumerate(parts):
        m = re.fullmatch(r"([%s])\s*[:.)—-]\s*(.+)" % LETTERS, x)
        if not m or m.group(1) != LETTERS[i]: sys.exit("варианты — по порядку с буквами: «А: …|Б: …»")
        out[m.group(1)] = text_ok(D, "вариант " + m.group(1), m.group(2), 120)
    return out


def add(a):
    D = _dela()
    vopros = text_ok(D, "вопрос", a.vopros, 160); var = variants(D, a.varianty)
    if a.vybrala not in var: sys.exit("выбранный вариант — одна из букв: %s" % ", ".join(var))
    pochemu = text_ok(D, "почему", a.pochemu, 160); peredelat = text_ok(D, "переделать", a.peredelat, 200)
    ne_zamok = text_ok(D, "не замок", a.ne_zamok, 120, need=False)
    u = ulika(D, a.ulika); t = now(a)
    whole = " · ".join([vopros, peredelat] + list(var.values()))
    mixed = MIXED.search(whole)
    if mixed: sys.exit("в тексте слово, где смешаны латинские и русские буквы (около «%s») — перепишите одним алфавитом" % whole[max(0, mixed.start() - 3):mixed.end() + 6])
    hit = ZAMOK.search(whole)
    def fn(rs, st):
        n = "R-%04d" % (max([int(r["n"][2:]) for r in rs] or [0]) + 1)
        if a.zamok or (hit and not ne_zamok):
            why = "помечено как замок" if a.zamok else "слово «%s»" % hit.group(0)
            row = {"n": n, "ts": t.isoformat(timespec="seconds"), "шаг": "отказ", "причина": why}
            return [row], "", ("это под замком (%s): развилкой не идёт — деньги, слово от имени хозяина, отправка, публикация и удаление "
                               "только через Согласование (карточка и его нажатие). Слово значит другое — скажите прямо: --ne-zamok \"почему\"" % why)
        row = {"n": n, "ts": t.isoformat(timespec="seconds"), "шаг": "точка", "вопрос": vopros, "варианты": var, "выбрано": a.vybrala, "почему": pochemu,
               "переделать": peredelat, "улика": u}
        if hit: row.update({"слово_замка": hit.group(0), "не_замок": ne_zamok})
        return [row], n, None
    locked(fn)


def switch(a):
    D = _dela(); u = ulika(D, a.ulika, ("msg",)); t = now(a)
    def fn(rs, st):
        p = st.get(a.n) if NUM.match(a.n or "") else None
        if p is None: return [], "", "такой развилки нет: %s" % a.n
        if not p["открыта"]: return [], "", "%s закрыта — курс там уже не меняется; новое решение — новой точкой" % a.n
        if a.na not in p["варианты"]: return [], "", "вариант — одна из букв: %s" % ", ".join(p["варианты"])
        if a.na == p["выбрано"]: return [], "", "по варианту %s уже иду — менять нечего" % a.na
        row = {"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "смена", "с": p["выбрано"], "на": a.na, "улика": u}
        return [row], "%s · курс сменён: %s → %s (%s). Переделать: %s" % (a.n, p["выбрано"], a.na, p["варианты"][a.na], p["переделать"]), None
    locked(fn)


def done(a):
    D = _dela(); pr = text_ok(D, "причина", a.prichina, 120); t = now(a)
    def fn(rs, st):
        p = st.get(a.n) if NUM.match(a.n or "") else None
        if p is None: return [], "", "такой развилки нет: %s" % a.n
        if not p["открыта"]: return [], "", "%s уже закрыта" % a.n
        return [{"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "закрыта", "причина": pr}], "%s · закрыта на варианте %s" % (a.n, p["выбрано"]), None
    locked(fn)


def read():
    try:
        with open(LOG, encoding="utf-8") as f: rs = rows(f)
    except OSError: rs = []
    return rs, state(rs)


def lst(a):
    _, st = read(); ps = [p for p in st.values() if p["открыта"] or not a.open]
    if not ps: print("открытых развилок нет" if a.open else "развилок нет"); return
    for p in sorted(ps, key=lambda p: p["n"]):
        print("%s · %s · иду по %s (%s)%s%s — при смене: %s" % (p["n"], p["вопрос"], p["выбрано"], p["варианты"][p["выбрано"]], "" if p["открыта"] else " · закрыта",
                                                                 " · смен %d" % p["смен"] if p["смен"] else "", p["переделать"]))


def itog(a):
    rs, st = read(); since = now(a) - dt.timedelta(days=a.days)
    out = {"точек": sum(1 for p in st.values() if p["ts"] >= since), "открыто": sum(1 for p in st.values() if p["открыта"]),
           "смен_курса": sum(1 for r in rs if r.get("шаг") == "смена" and when(r) >= since),
           "закрыто": sum(1 for p in st.values() if p["закрыта_ts"] and p["закрыта_ts"] >= since),
           "отказов_замка": sum(1 for r in rs if r.get("шаг") == "отказ" and when(r) >= since)}
    if a.json: print(json.dumps(out, ensure_ascii=False)); return
    print("за %d дн.: точек %d · открыто %d · смен курса %d · закрыто %d · отказов «под замком» %d" % (a.days, out["точек"], out["открыто"], out["смен_курса"], out["закрыто"], out["отказов_замка"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    for k in ("--vopros", "--varianty", "--vybrala", "--pochemu", "--peredelat", "--ulika", "--ne-zamok", "--now"): p.add_argument(k)
    p.add_argument("--zamok", action="store_true")
    p = sp.add_parser("switch"); p.add_argument("n"); p.add_argument("--na"); p.add_argument("--ulika"); p.add_argument("--now")
    p = sp.add_parser("done"); p.add_argument("n"); p.add_argument("--prichina"); p.add_argument("--now")
    p = sp.add_parser("list"); p.add_argument("--open", action="store_true")
    p = sp.add_parser("itog"); p.add_argument("--days", type=int, default=7); p.add_argument("--json", action="store_true"); p.add_argument("--now")
    a = ap.parse_args()
    {"add": add, "switch": switch, "done": done, "list": lst, "itog": itog}[a.cmd](a)
