#!/usr/bin/env python3
"""Журнал проблем Милы с циклом улучшения: найдено → причина → правка → проверено → закрыто, каждая ступень с уликой.
Файл work/problemy.jsonl в доме Милы (600), только дописывается; номер и запись — под одним замком.
  problemy.py add --chto <факт ≤160> --gde <место> --kto-nashel сама|хозяин|человек|проверка --ulika <указатель>   → P-0001
  problemy.py why P-0001 --prichina <≤160> --klass <класс>
  problemy.py fix P-0001 --pravka <что изменено ≤160> --vid обещание|навык|проверка|хук|настройка --ulika <указатель>
  problemy.py verify P-0001 --ulika <указатель: прогон или повторённый случай>    # другая улика и позже правки
  problemy.py close P-0001                                                        # только после «проверено»
  problemy.py reopen P-0001 --ulika <указатель>                                   # повторилось после закрытия: круг заново
  problemy.py reclass P-0001 --klass <класс> --prichina <≤160>                    # другая причина — строкой в журнал
  problemy.py list [--open] · itog [--days 7] [--json] · povtory [--json]
Места: личка, группа, письмо, документ, расписание, память, деньги, инструмент, другое.
Классы: память, проверка, инструмент, текст, срок, чужое-действие, другое.
Третий случай одного класса в одном месте (новая проблема и повтор закрытой — один счёт; «другое» тоже считается) обещанием
не закрывается: правка — навык, проверка, хук или настройка. Отказ и смена класса после него остаются в журнале;
проблема считается по каждому классу, который носила, — сменой класса правило не обойти.
Улика — указатель, а не текст (правила dela.py): msg:<чат>:<id>, file:<путь в work>, commit:<хэш>, link:https://…, journal:<файл>:<строка>.
В текстах — роль, не имя («клиент», «гость»); телефоны, почта, @ники — отказ. Only stdlib."""
import argparse, datetime as dt, fcntl, importlib.util, json, os, re, sys

H = os.path.dirname(os.path.abspath(__file__))
HOME_WORK = os.path.expanduser(os.environ.get("MILA_WORK", "~/work"))
LOG = os.path.join(HOME_WORK, "problemy.jsonl")
MESTA = ("личка", "группа", "письмо", "документ", "расписание", "память", "деньги", "инструмент", "другое")
KLASSY = ("память", "проверка", "инструмент", "текст", "срок", "чужое-действие", "другое")
KTO = ("сама", "хозяин", "человек", "проверка")
VIDY = ("обещание", "навык", "проверка", "хук", "настройка")
MEHANIZM = ("навык", "проверка", "хук", "настройка")
GENERIC = {"ошибка", "сбой", "проблема", "дефект", "косяк", "баг", "не работает", "error", "bug", "problem", "failure"}
NUM = re.compile(r"^P-\d{4,6}$")


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


def when(row):
    try: t = dt.datetime.fromisoformat(str(row.get("ts") or ""))
    except ValueError: return None
    return t if t.tzinfo else t.astimezone()


def rows(f):
    """every whole line of the journal; a broken line is skipped, never fatal."""
    f.seek(0); res = []
    for l in f.read().splitlines():
        try: r = json.loads(l)
        except ValueError: continue
        if isinstance(r, dict) and NUM.match(str(r.get("n") or "")) and when(r) is not None: res.append(r)
    return res


def state(rs):
    """per problem: stage, fields, and the count of cases (a new problem and every reopen — one count)."""
    st = {}
    for r in rs:
        n, s = r["n"], r.get("шаг")
        p = st.get(n)
        if s == "найдено" and p is None:
            st[n] = {"n": n, "шаг": "найдено", "что": r.get("что"), "место": r.get("место"), "кто": r.get("кто"), "класс": None, "классы": [], "случаи": [when(r)],
                     "найдено": when(r), "вид": None, "улика_правки": None, "правка_ts": None, "закрыто": None, "отказ": False}
        elif p is None: continue
        elif s == "причина" and p["шаг"] == "найдено": p.update({"шаг": "причина", "класс": r.get("класс")}); p["классы"].append(r.get("класс"))
        elif s == "переклассификация" and p["шаг"] in ("причина", "правка", "проверено"): p["класс"] = r.get("класс"); p["классы"].append(r.get("класс"))
        elif s == "правка" and p["шаг"] == "причина": p.update({"шаг": "правка", "вид": r.get("вид"), "улика_правки": r.get("улика"), "правка_ts": when(r)})
        elif s == "проверено" and p["шаг"] == "правка": p["шаг"] = "проверено"
        elif s == "закрыто" and p["шаг"] == "проверено": p.update({"шаг": "закрыто", "закрыто": when(r)})
        elif s == "повтор" and p["шаг"] == "закрыто": p.update({"шаг": "найдено", "закрыто": None, "вид": None, "улика_правки": None, "правка_ts": None}); p["случаи"].append(when(r))
        elif s == "отказ": p["отказ"] = True
    return st


def cases(st, klass, mesto):
    """a problem counts under every class it has carried: a change of class does not take its cases out of the count."""
    return sum(len(p["случаи"]) for p in st.values() if klass in p["классы"] and p["место"] == mesto)


def text_ok(D, name, v, need=True):
    v = (v or "").strip()
    if not v:
        if need: sys.exit("«%s» — пусто" % name)
        return v
    if len(v) > 160: sys.exit("«%s» — коротко, до 160 знаков" % name)
    if "\n" in v or "\r" in v: sys.exit("«%s» — одной строкой" % name)
    if D.pd_hit(v): sys.exit("в поле «%s» личные данные — роль вместо имени («клиент», «гость»), без номеров и адресов" % name)
    return v


def ulika(D, u, kinds=None):
    u = (u or "").strip()
    if not u or not D.ULIKA.match(u): sys.exit("нет улики — не пишу (msg:… | file:… | link:… | journal:… | commit:…)")
    if kinds and u.split(":", 1)[0] not in kinds: sys.exit("улика этой ступени — %s" % " или ".join(k + ":" for k in kinds))
    if not D.ulika_ok(u): sys.exit("улика не сходится: файл — внутри work и существует; commit — хэш; msg — <чат>:<номер>; link — https")
    return u


def locked(a, fn):
    """read the whole journal, decide and append — under one lock: two writers never take the same number or the same stage."""
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


def need(st, n, stage, word):
    if not NUM.match(n or ""): sys.exit("номер — P-0001")
    p = st.get(n)
    if p is None: return None, "такой проблемы нет: %s" % n
    if p["шаг"] != stage: return None, "%s сейчас на ступени «%s» — %s" % (n, p["шаг"], word)
    return p, None


def add(a):
    D = _dela()
    chto = text_ok(D, "что", a.chto)
    if chto.lower().strip(" .!") in GENERIC: sys.exit("«что» — факт, а не общее слово: что именно случилось")
    if a.gde not in MESTA: sys.exit("место — одно из: %s" % ", ".join(MESTA))
    if a.kto_nashel not in KTO: sys.exit("кто нашёл — одно из: %s" % ", ".join(KTO))
    u = ulika(D, a.ulika); t = now(a)
    def fn(rs, st):
        n = "P-%04d" % (max([int(r["n"][2:]) for r in rs] or [0]) + 1)
        return [{"n": n, "ts": t.isoformat(timespec="seconds"), "шаг": "найдено", "что": chto, "место": a.gde, "кто": a.kto_nashel, "улика": u}], n, None
    locked(a, fn)


def why(a, step="причина"):
    D = _dela()
    pr = text_ok(D, "причина", a.prichina)
    if a.klass not in KLASSY: sys.exit("класс — один из: %s" % ", ".join(KLASSY))
    t = now(a)
    def fn(rs, st):
        if step == "причина":
            p, e = need(st, a.n, "найдено", "причину называют сразу после «найдено»")
        else:
            p = st.get(a.n) if NUM.match(a.n or "") else None
            e = None if p and p["шаг"] in ("причина", "правка", "проверено") else "сменить класс можно у проблемы с причиной и до закрытия: %s" % a.n
            if not e and p["класс"] == a.klass: e = "класс тот же — менять нечего"
        if e: return [], "", e
        row = {"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": step, "причина": pr, "класс": a.klass}
        if step == "переклассификация": row.update({"был": p["класс"], "после_отказа": bool(p["отказ"])})
        return [row], "%s · %s: %s" % (a.n, step, a.klass), None
    locked(a, fn)


def fix(a):
    D = _dela()
    pravka = text_ok(D, "правка", a.pravka)
    if a.vid not in VIDY: sys.exit("вид правки — один из: %s" % ", ".join(VIDY))
    u = ulika(D, a.ulika, ("msg", "file") if a.vid == "обещание" else ("file", "commit")); t = now(a)
    def fn(rs, st):
        p, e = need(st, a.n, "причина", "правка идёт после причины")
        if e: return [], "", e
        k, kl = max((cases(st, c, p["место"]), c) for c in set(p["классы"]))   # every class the problem has carried: a change of class opens no way round
        if a.vid == "обещание" and k >= 3:
            row = {"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "отказ", "класс": kl, "место": p["место"], "случаев": k}
            return [row], "", "третий раз (случаев: %d · %s · %s) — обещанием не закрываю, нужен механизм: навык, проверка, хук или настройка" % (k, kl, p["место"])
        return [{"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "правка", "правка": pravka, "вид": a.vid, "улика": u}], "%s · правка: %s" % (a.n, a.vid), None
    locked(a, fn)


def verify(a):
    D = _dela(); u = ulika(D, a.ulika); t = now(a)
    def fn(rs, st):
        p, e = need(st, a.n, "правка", "проверяют после правки")
        if e: return [], "", e
        if u == p["улика_правки"]: return [], "", "улика проверки — не та же, что у правки: прогон или повторённый случай"
        if p["правка_ts"] is None or t <= p["правка_ts"]: return [], "", "проверка — позже правки по времени"
        return [{"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "проверено", "улика": u}], "%s · проверено" % a.n, None
    locked(a, fn)


def close(a):
    t = now(a)
    def fn(rs, st):
        p, e = need(st, a.n, "проверено", "закрываю только проверенное")
        if e: return [], "", e
        return [{"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "закрыто"}], "%s · закрыто" % a.n, None
    locked(a, fn)


def reopen(a):
    D = _dela(); u = ulika(D, a.ulika); t = now(a)
    def fn(rs, st):
        p, e = need(st, a.n, "закрыто", "повтор пишут у закрытой; у открытой — продолжайте круг")
        if e: return [], "", e
        return [{"n": a.n, "ts": t.isoformat(timespec="seconds"), "шаг": "повтор", "улика": u}], "%s · повтор, случай №%d — причина заново" % (a.n, len(p["случаи"]) + 1), None
    locked(a, fn)


def read():
    try:
        with open(LOG, encoding="utf-8") as f: rs = rows(f)
    except OSError: rs = []
    return rs, state(rs)


def lst(a):
    _, st = read()
    ps = [p for p in st.values() if not a.open or p["шаг"] != "закрыто"]
    if not ps: print("проблем нет" if not a.open else "открытых проблем нет"); return
    for p in sorted(ps, key=lambda p: p["n"]):
        print("%s · %s · %s/%s · %s%s" % (p["n"], p["шаг"], p["класс"] or "—", p["место"], p["что"], " · случаев %d" % len(p["случаи"]) if len(p["случаи"]) > 1 else ""))


def repeats(st):
    seen = {}
    for p in st.values():
        for c in set(p["классы"]): seen[(c, p["место"])] = seen.get((c, p["место"]), 0) + len(p["случаи"])
    return {k: v for k, v in seen.items() if v >= 3}


def itog(a):
    rs, st = read(); t = now(a); since = t - dt.timedelta(days=a.days)
    out = {"найдено": sum(1 for p in st.values() if p["найдено"] >= since),
           "закрыто": sum(1 for p in st.values() if p["закрыто"] and p["закрыто"] >= since),
           "открыто": sum(1 for p in st.values() if p["шаг"] != "закрыто"),
           "открыто_старше_7_дней": sum(1 for p in st.values() if p["шаг"] != "закрыто" and p["случаи"][-1] < t - dt.timedelta(days=7)),
           "повторы": sum(1 for r in rs if r.get("шаг") == "повтор" and when(r) >= since),
           "отказы_третьего_раза": sum(1 for r in rs if r.get("шаг") == "отказ" and when(r) >= since),
           "смен_класса_после_отказа": sum(1 for r in rs if r.get("шаг") == "переклассификация" and r.get("после_отказа") and when(r) >= since),
           "нужен_механизм": len(repeats(st))}
    if a.json: print(json.dumps(out, ensure_ascii=False)); return
    print("за %d дн.: найдено %d · закрыто %d · открыто %d (старше 7 дней — %d) · повторов %d · отказов третьего раза %d · смен класса после отказа %d · нужен механизм: %d"
          % (a.days, out["найдено"], out["закрыто"], out["открыто"], out["открыто_старше_7_дней"], out["повторы"], out["отказы_третьего_раза"],
             out["смен_класса_после_отказа"], out["нужен_механизм"]))


def povtory(a):
    _, st = read(); rep = repeats(st)
    if a.json: print(json.dumps([{"класс": k, "место": m, "случаев": v} for (k, m), v in sorted(rep.items())], ensure_ascii=False)); return
    if not rep: print("трёх случаев одного класса в одном месте нет"); return
    for (k, m), v in sorted(rep.items(), key=lambda x: -x[1]): print("%s · %s: %d случаев — нужен механизм" % (k, m, v))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    def cmd(name, *args, n=True):
        p = sp.add_parser(name)
        if n: p.add_argument("n")
        for x in args: p.add_argument(x)
        p.add_argument("--now", help=argparse.SUPPRESS)
        return p
    cmd("add", "--chto", "--gde", "--kto-nashel", "--ulika", n=False)
    cmd("why", "--prichina", "--klass"); cmd("reclass", "--prichina", "--klass")
    cmd("fix", "--pravka", "--vid", "--ulika"); cmd("verify", "--ulika"); cmd("close"); cmd("reopen", "--ulika")
    cmd("list", n=False).add_argument("--open", action="store_true")
    i = cmd("itog", n=False); i.add_argument("--days", type=int, default=7); i.add_argument("--json", action="store_true")
    cmd("povtory", n=False).add_argument("--json", action="store_true")
    a = ap.parse_args()
    {"add": add, "why": why, "reclass": lambda a: why(a, "переклассификация"), "fix": fix, "verify": verify, "close": close, "reopen": reopen,
     "list": lst, "itog": itog, "povtory": povtory}[a.cmd](a)
