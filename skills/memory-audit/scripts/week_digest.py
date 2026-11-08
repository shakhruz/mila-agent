#!/usr/bin/env python3
"""week_digest.py — seven day pages into one week page, without a model: deeds by type per day and in sum, the days' NOW lines,
what memory learned; each day linked. A model may shorten it later — the facts stay in the day files.

  python3 week_digest.py [--work ~/work] [--week YYYY-Www]     (default: last week, ISO)

Reads work/memory/days/<date>.md written by day_digest.py; writes work/memory/weeks/<YYYY>-W<ww>.md (≤ 3 KB).
Same input — same file; nothing is deleted."""
import argparse, collections, datetime, os, re, sys

LIMIT = 3072


def days_of(week):
    y, w = week.split("-W")
    mon = datetime.date.fromisocalendar(int(y), int(w), 1)
    return [mon + datetime.timedelta(days=i) for i in range(7)]


def parse_day(text):
    """(deeds count, {type: n}, NOW lines, memory files) from a day page; anything unknown is skipped."""
    m = re.search(r"^## Сделано — (\d+) дел(?:: (.*))?$", text, re.M)
    total = int(m.group(1)) if m else 0
    types = collections.Counter()
    for part in ((m.group(2) or "").split(", ") if m else []):
        mm = re.fullmatch(r"(.+) (\d+)", part.strip())
        if mm: types[mm.group(1)] += int(mm.group(2))
    def section(title):
        s = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(title), text, re.M | re.S)
        return [l[2:].strip() for l in (s.group(1).splitlines() if s else []) if l.startswith("- ") and not l.startswith("- …")]
    now = [l for l in section("Ход дня (NOW.md)") if l != "строк за день нет"]
    mem = [l for l in section("Узнала (memory/)") if l != "новых и изменённых нет"]
    return total, types, now, mem


def render(week, rows):
    total = sum(r[1] for r in rows); types = collections.Counter()
    for r in rows: types.update(r[2])
    lines = ["# Неделя %s" % week, "", "## Сделано — %d дел" % total + (": " + ", ".join("%s %d" % kv for kv in types.most_common()) if total else "")]
    for d, n, t, now, mem, have in rows:
        lines.append("- %s · %s" % (d.isoformat(), ("%d дел — [день](../days/%s.md)" % (n, d.isoformat())) if have else "страницы дня нет"))
    lines += ["", "## Ход недели"]
    for d, n, t, now, mem, have in rows:
        for l in now[:2]: lines.append("- %s %s" % (d.strftime("%d.%m"), l[:110]))
    lines += ["", "## Узнала за неделю"] + (["- " + x for x in sorted({x for r in rows for x in r[4]})[:12]] or ["- новых и изменённых нет"])
    out, size, tail = [], 0, "- …дальше обрезано: потолок 3 КБ; полностью — в страницах дней"
    for l in lines:
        b = len((l + "\n").encode("utf-8"))
        if size + b > LIMIT - len(tail.encode("utf-8")) - 1:
            out.append(tail); break
        out.append(l); size += b
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    last = datetime.date.today() - datetime.timedelta(days=7); y, w, _ = last.isocalendar()
    ap.add_argument("--work", default=os.path.expanduser("~/work"))
    ap.add_argument("--week", default="%d-W%02d" % (y, w))
    a = ap.parse_args()
    if not re.fullmatch(r"\d{4}-W\d{2}", a.week): sys.exit("--week: YYYY-Www")
    try: ds = days_of(a.week)
    except ValueError: sys.exit("--week: нет такой недели")
    rows = []
    for d in ds:
        p = os.path.join(a.work, "memory", "days", d.isoformat() + ".md")
        try:
            if os.path.islink(p): raise OSError
            txt = open(p, encoding="utf-8").read(16384); rows.append((d,) + parse_day(txt) + (True,))
        except OSError:
            rows.append((d, 0, collections.Counter(), [], [], False))
    wd = os.path.join(a.work, "memory", "weeks"); os.makedirs(wd, mode=0o700, exist_ok=True)
    p = os.path.join(wd, a.week + ".md"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write(render(a.week, rows))
    os.chmod(tmp, 0o600); os.replace(tmp, p)
    print(p)


if __name__ == "__main__":
    main()
