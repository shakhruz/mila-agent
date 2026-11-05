#!/usr/bin/env python3
"""The owner's decisions journal (decisions.jsonl) — a hash chain the session cannot rewrite unseen.

Every line: n (1, 2, …), ts, the event and its fields, prev (the previous line's h, "" for the first) and
h = sha256(prev + the line's canonical JSON without h). Changing, inserting or removing a line breaks the chain from there on;
cutting the tail is seen against an anchor «n:h12» kept outside the machine (the owner's evening summary).
Only the consent proxy (mila-io) writes it; the file is 0640, its folder not writable by the session.

  decisions.py verify FILE [--anchor N:H12]   → ok n head, or the first bad line; exit 1 on a break
  decisions.py head FILE                      → «n:h12» for the anchor"""
import fcntl, hashlib, json, os, sys, time


def _canon(row):
    return json.dumps({k: v for k, v in row.items() if k != "h"}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(prev, row):
    return hashlib.sha256((prev + _canon(row)).encode("utf-8")).hexdigest()


def _last(path):
    """(n, h) of the last line; (0, "") for an empty or missing file."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 65536))
            lines = [l for l in f.read().splitlines() if l.strip()]
    except OSError:
        return 0, ""
    if not lines: return 0, ""
    r = json.loads(lines[-1])
    return int(r["n"]), str(r["h"])


def append(path, row, mode=0o640, now=None):
    """add one decision; returns the written line (with n, prev, h)"""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, mode)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.fchmod(fd, mode)   # whatever the umask: the session's group reads, nobody else writes
        n, prev = _last(path)
        line = dict(row, n=n + 1, ts=int(now if now is not None else time.time()), prev=prev)
        line["h"] = _hash(prev, line)
        os.write(fd, (json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
        return line
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


def verify(path, anchor=""):
    """(ok, n, head12, problem). anchor «N:H12»: the line N must be there with that hash (a cut tail or a rewrite shows)."""
    prev, n, seen = "", 0, {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    for i, raw in enumerate(lines, 1):
        if not raw.strip(): continue
        try: r = json.loads(raw)
        except ValueError: return False, n, prev[:12], "line %d: not JSON" % i
        if r.get("n") != n + 1: return False, n, prev[:12], "line %d: n=%s, expected %d (a line removed or inserted)" % (i, r.get("n"), n + 1)
        if r.get("prev") != prev: return False, n, prev[:12], "line %d: prev does not match the line before" % i
        if r.get("h") != _hash(prev, r): return False, n, prev[:12], "line %d: changed after it was written" % i
        prev, n = r["h"], r["n"]; seen[n] = prev
    if anchor:
        try: an, ah = anchor.split(":", 1); an = int(an)
        except ValueError: return False, n, prev[:12], "anchor: expected N:H12"
        if an > n: return False, n, prev[:12], "the journal ends at %d, the anchor says %d — the tail was cut" % (n, an)
        if not seen.get(an, "").startswith(ah): return False, n, prev[:12], "line %d does not match the anchor — rewritten" % an
    return True, n, prev[:12], ""


def main(argv):
    if len(argv) >= 2 and argv[0] in ("verify", "head"):
        if argv[0] == "head":
            n, h = _last(argv[1]); print("%d:%s" % (n, h[:12])); return 0
        anchor = argv[argv.index("--anchor") + 1] if "--anchor" in argv else ""
        ok, n, head, why = verify(argv[1], anchor)
        print(("ok %d %s" % (n, head)) if ok else ("broken: " + why)); return 0 if ok else 1
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
