#!/usr/bin/env python3
"""month_digest.py — the week pages of a month into one month page, without a model: deeds by type per week and in sum,
each week linked, what memory learned. The facts stay in the day and week pages.

  python3 month_digest.py [--work ~/work] [--month YYYY-MM]     (default: last month)

Reads work/memory/weeks/<YYYY>-W<ww>.md (week_digest.py) for every ISO week that has a day in the month; writes
work/memory/months/<YYYY-MM>.md (≤ 3 KB). Same input — same file; nothing is deleted."""
import argparse, collections, datetime, os, re, sys

LIMIT = 3072


def weeks_of(month):
    y, m = map(int, month.split("-"))
    d = datetime.date(y, m, 1); seen = []
    while d.month == m:
        iy, iw, _ = d.isocalendar(); k = "%d-W%02d" % (iy, iw)
        if k not in seen: seen.append(k)
        d += datetime.timedelta(days=1)
    return seen


def parse_week(text):
    m = re.search(r"^## Сделано — (\d+) дел(?:: (.*))?$", text, re.M)
    total = int(m.group(1)) if m else 0
    types = collections.Counter()
    for part in ((m.group(2) or "").split(", ") if m else []):
        mm = re.fullmatch(r"(.+) (\d+)", part.strip())
        if mm: types[mm.group(1)] += int(mm.group(2))
    s = re.search(r"^## Узнала за неделю\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    mem = [l[2:].strip() for l in (s.group(1).splitlines() if s else []) if l.startswith("- ") and not l.startswith("- …") and l[2:].strip() != "новых и изменённых нет"]
    return total, types, mem


def main():
    ap = argparse.ArgumentParser()
    first = datetime.date.today().replace(day=1); prev = (first - datetime.timedelta(days=1)).strftime("%Y-%m")
    ap.add_argument("--work", default=os.path.expanduser("~/work")); ap.add_argument("--month", default=prev)
    a = ap.parse_args()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", a.month): sys.exit("--month: YYYY-MM")
    rows = []
    for wk in weeks_of(a.month):
        p = os.path.join(a.work, "memory", "weeks", wk + ".md")
        try:
            if os.path.islink(p): raise OSError
            rows.append((wk,) + parse_week(open(p, encoding="utf-8").read(16384)) + (True,))
        except OSError:
            rows.append((wk, 0, collections.Counter(), [], False))
    total = sum(r[1] for r in rows); types = collections.Counter()
    for r in rows: types.update(r[2])
    lines = ["# Месяц %s" % a.month, "", "## Сделано — %d дел" % total + (": " + ", ".join("%s %d" % kv for kv in types.most_common()) if total else ""),
             "(недели на стыке месяцев считаются целиком)"]
    for wk, n, t, mem, have in rows:
        lines.append("- %s · %s" % (wk, ("%d дел — [неделя](../weeks/%s.md)" % (n, wk)) if have else "страницы недели нет"))
    lines += ["", "## Узнала за месяц"] + (["- " + x for x in sorted({x for r in rows for x in r[3]})[:20]] or ["- новых и изменённых нет"])
    out, size, tail = [], 0, "- …дальше обрезано: потолок 3 КБ; полностью — в страницах недель"
    for l in lines:
        b = len((l + "\n").encode("utf-8"))
        if size + b > LIMIT - len(tail.encode("utf-8")) - 1:
            out.append(tail); break
        out.append(l); size += b
    md = os.path.join(a.work, "memory", "months"); os.makedirs(md, mode=0o700, exist_ok=True)
    p = os.path.join(md, a.month + ".md"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600); os.replace(tmp, p)
    print(p)


if __name__ == "__main__":
    main()
