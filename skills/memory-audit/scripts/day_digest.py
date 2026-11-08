#!/usr/bin/env python3
"""day_digest.py — the day in one page, every night, without a model: what was done, what is open, what changed in memory.

  python3 day_digest.py [--work ~/work] [--date YYYY-MM-DD]     (default: yesterday by the local clock)

Reads only this Mila's own journals: work/dela.jsonl (deeds with proof), the NOW.md lines of that day («- DD.MM …»),
the files in memory/ changed that day. Writes work/memory/days/<date>.md (≤ 2 KB). Nothing from chats is copied — a deed's
name, type and proof pointer, not what people wrote. Running it twice gives the same file; nothing is deleted.
Set it for the night with raspisanie (mila_cron.py), e.g. 03:15."""
import argparse, collections, datetime, json, os, re, sys

LIMIT = 2048


def deeds(work, day):
    out = []
    try:
        for line in open(os.path.join(work, "dela.jsonl"), encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("дата") == day:
                out.append(r)
    except OSError:
        pass
    return out


def now_lines(work, day):
    d = datetime.date.fromisoformat(day)
    mark = re.compile(r"^-\s*(?:ТИК\s+)?%02d\.%02d\b" % (d.day, d.month))
    try:
        return [l.strip() for l in open(os.path.join(work, "NOW.md"), encoding="utf-8") if mark.match(l.strip())]
    except OSError:
        return []


def memory_changed(work, day):
    d = datetime.date.fromisoformat(day); lo = datetime.datetime.combine(d, datetime.time()).timestamp(); hi = lo + 86400
    m = os.path.join(work, "memory"); out = []
    for root, dirs, files in os.walk(m):
        dirs[:] = [x for x in dirs if x not in ("days", "weeks", "months")]
        for f in files:
            if f.endswith(".md") and f != "MEMORY.md":
                p = os.path.join(root, f)
                try:
                    if lo <= os.stat(p).st_mtime < hi: out.append(os.path.relpath(p, m))
                except OSError:
                    pass
    return sorted(out)


def render(day, ds, nl, mc):
    by_type = collections.Counter(r.get("тип") or "—" for r in ds)
    by_step = collections.Counter(r.get("ступень") or "—" for r in ds)
    lines = ["# День %s" % day, ""]
    lines.append("## Сделано — %d дел" % len(ds) + (": " + ", ".join("%s %d" % kv for kv in sorted(by_type.items())) if ds else ""))
    if ds:
        lines.append("Ступени: " + ", ".join("%s %d" % kv for kv in sorted(by_step.items())))
        for r in ds[:12]:
            lines.append("- %s · %s · %s" % (str(r.get("дело"))[:70], r.get("ступень") or "—", str(r.get("улика"))[:60]))
        if len(ds) > 12:
            lines.append("- …и ещё %d (work/dela.jsonl, дата %s)" % (len(ds) - 12, day))
    lines += ["", "## Ход дня (NOW.md)"] + (["- " + l.lstrip("- ")[:130] for l in nl[:8]] or ["- строк за день нет"])
    lines += ["", "## Узнала (memory/)"] + (["- " + x for x in mc[:10]] or ["- новых и изменённых нет"])
    out, size, tail = [], 0, "- …дальше обрезано: потолок 2 КБ"
    for l in lines:   # the ceiling: whole lines only, the cut said in the file
        b = len((l + "\n").encode("utf-8"))
        if size + b > LIMIT - len(tail.encode("utf-8")) - 1:
            out.append(tail); break
        out.append(l); size += b
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.path.expanduser("~/work"))
    ap.add_argument("--date", default=(datetime.date.today() - datetime.timedelta(days=1)).isoformat())
    a = ap.parse_args()
    try:
        datetime.date.fromisoformat(a.date)
    except ValueError:
        sys.exit("--date: YYYY-MM-DD")
    text = render(a.date, deeds(a.work, a.date), now_lines(a.work, a.date), memory_changed(a.work, a.date))
    d = os.path.join(a.work, "memory", "days"); os.makedirs(d, mode=0o700, exist_ok=True)
    p = os.path.join(d, a.date + ".md"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: f.write(text)
    os.chmod(tmp, 0o600); os.replace(tmp, p)
    print(p)


if __name__ == "__main__":
    main()
