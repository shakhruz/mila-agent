#!/usr/bin/env python3
"""Учёт дел Милы: что сделала, взял ли человек, что стало — каждое с уликой. Файл work/dela.jsonl в доме Милы (600), только дописывается.
  dela.py add --delo <уникальное имя> --tip <тип> --dlya <для кого: ярлык, не имя> --ulika <указатель> --stupen сделала|приняли|результат [--rezultat "…"] [--data ГГГГ-ММ-ДД]
  dela.py itog [--days 7] [--json]      → по типам: сделала ≥ приняли ≥ результат (накопительно), только числа
Отказ: нет улики; ступень не из трёх; в «для», «результат» или «дело» — телефон, почта, карта, паспорт, @ник или 9+ цифр подряд;
«дело» — общее слово (пост, КП, отчёт…) без даты или номера — склеит разные дела; «результат» длиннее 160 знаков.
Улика — указатель, а не текст: msg:<чат>:<id>, file:<путь>, link:<https://…>, journal:<файл>:<строка>. Текст переписки в журнал не копируется."""
import argparse, datetime as dt, fcntl, json, os, re, sys

HOME_WORK = os.path.expanduser(os.environ.get("MILA_WORK", "~/work"))
LOG = os.path.join(HOME_WORK, "dela.jsonl")
STEPS = {"сделала": 1, "приняли": 2, "результат": 3}
GENERIC = {"пост", "кп", "отчёт", "отчет", "письмо", "звонок", "встреча", "сообщение", "задача", "дело", "post", "report", "email", "call", "task"}
PD = re.compile(r"\d[\d \-()]{7,}\d|@\w{3,}|[\w.+-]+@[\w-]+\.[\w.]+|\b[A-Z]{2}\d{7}\b")
ULIKA = re.compile(r"^(msg|file|link|journal|kassa|commit):\S{1,300}$")
DLYA = re.compile(r"^(⟦[^⟧]{1,40}⟧|[a-zа-яё0-9\-]{1,40}(·[a-zа-яё0-9]{1,20})?)$")   # ярлык pd-vault или ОДНО слово-тип: «турфирма», «гость», «лид·12» — «иван петров» не пройдёт
TZ = dt.timezone(dt.timedelta(hours=5))


def pd_hit(text):
    t = str(text or "")
    if PD.search(t):
        return True
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pd-vault"))
        from pd_vault import find
        return bool(find(t))
    except Exception:
        return False


def ulika_ok(u):
    """Улика должна указывать на то, что есть: файл — внутри work и существует; коммит — хэш; сообщение — чат и номер."""
    kind, _, ref = u.partition(":")
    if kind in ("file", "journal"):
        path = ref.split(":")[0] if kind == "journal" else ref
        base = os.path.realpath(HOME_WORK); full = os.path.realpath(os.path.join(HOME_WORK, path) if not os.path.isabs(path) else path)
        return os.path.commonpath([base, full]) == base and os.path.isfile(full)
    if kind == "commit":
        return bool(re.fullmatch(r"[0-9a-f]{7,40}", ref))
    if kind == "msg":
        return bool(re.fullmatch(r"[^:\s]{1,64}:\d{1,12}", ref))
    if kind == "link":
        return ref.startswith("https://")
    return kind == "kassa" and bool(re.fullmatch(r"[\w.\-]{1,64}", ref))


def add(a):
    if a.stupen not in STEPS:
        sys.exit("ступень — сделала, приняли или результат")
    if not a.ulika or not ULIKA.match(a.ulika):
        sys.exit("нет улики — дело не пишу (msg:… | file:… | link:… | journal:… | kassa:… | commit:…)")
    if not ulika_ok(a.ulika):
        sys.exit("улика не сходится: файл — внутри work и существует; commit — хэш; msg — <чат>:<номер>; link — https")
    if a.dlya and not DLYA.match(a.dlya.strip()):
        sys.exit("«для» — ярлык ⟦…⟧ или одно слово-тип («турфирма», «гость», «лид·12»), не имя человека")
    d = (a.delo or "").strip()
    if not d or (d.lower() in GENERIC):
        sys.exit("«дело» — уникальное имя: имя + дата или номер (не просто «%s»)" % d)
    for f, v in (("дело", d), ("для", a.dlya), ("результат", a.rezultat)):
        if pd_hit(v):
            sys.exit("в поле «%s» личные данные — ярлык вместо имени, номера и адреса" % f)
    if a.rezultat and len(a.rezultat) > 160:
        sys.exit("результат — коротко, до 160 знаков")
    row = {"дата": a.data or dt.datetime.now(TZ).date().isoformat(), "дело": d[:120], "тип": (a.tip or "другое")[:40], "для": (a.dlya or "")[:60],
           "ступень": a.stupen, "улика": a.ulika, "результат": (a.rezultat or "")[:160]}
    try:
        for l in open(LOG, encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if r.get("дело") == row["дело"] and r.get("ступень") == row["ступень"]:
                sys.exit("уже записано: %s · %s" % (row["дело"], row["ступень"]))
    except OSError:
        pass
    os.makedirs(HOME_WORK, exist_ok=True)
    fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX); f.write(json.dumps(row, ensure_ascii=False) + "\n"); fcntl.flock(f, fcntl.LOCK_UN)
    print("записала: %s · %s" % (d, a.stupen))


def itog(a):
    since = (dt.datetime.now(TZ).date() - dt.timedelta(days=a.days - 1)).isoformat()
    best = {}
    try:
        lines = open(LOG, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    for l in lines:
        try: r = json.loads(l)
        except ValueError: continue
        if str(r.get("дата", "")) < since or r.get("ступень") not in STEPS or not r.get("улика"):
            continue
        k = (r.get("тип") or "другое", r.get("дело"))
        best[k] = max(best.get(k, 0), STEPS[r["ступень"]])
    out = {}
    for (t, _), rank in best.items():
        c = out.setdefault(t, {"сделала": 0, "приняли": 0, "результат": 0})
        for st, k in STEPS.items():
            if k <= rank: c[st] += 1
    if a.json:
        print(json.dumps(out, ensure_ascii=False)); return
    if not out:
        print("дел с уликой за %d дн. нет" % a.days); return
    for t, c in sorted(out.items(), key=lambda x: -x[1]["сделала"]):
        print("%s: сделала %d · приняли %d · результат %d" % (t, c["сделала"], c["приняли"], c["результат"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    for k in ("--delo", "--tip", "--dlya", "--ulika", "--stupen", "--rezultat", "--data"): p.add_argument(k)
    i = sp.add_parser("itog"); i.add_argument("--days", type=int, default=7); i.add_argument("--json", action="store_true")
    a = ap.parse_args(); {"add": add, "itog": itog}[a.cmd](a)
