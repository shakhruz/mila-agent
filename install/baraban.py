#!/usr/bin/env python3
"""The Scheduler (RU: «Планировщик»; the file and the state keep the old name, baraban) — the schedule service outside the Claude Code session. Jobs a Mila set with mila-cron (~/work/schedule/jobs.json)
reach her as events in the plugin's journal, the same way rituals and ticks do; a session restart loses nothing.

  baraban.py tick --home H [--slug S] [--owner ID] [--state DIR] [--now ISO]   # one pass; a systemd timer runs it every minute
  baraban.py status --home H [--state DIR]                                    # jobs, last fire, last done, overdue
Rules (the same contract mila-cron and its skill describe):
- a job fires when its cron slot (in the owner's time zone, USER.md «Часовой пояс — …», else Asia/Tashkent) is newer than the
  last fire and newer than the job's creation; several missed slots → ONE event (catchup «one»), or none if catchup «skip»
  and the slot is older than 5 minutes;
- quiet hours (USER.md «Тихие часы — 22:00–08:00», else 22–08) and quiet «respect»: the slot waits until the quiet hours end
  and then fires once;
- expired job: one event «продлить?» and silence after it;
- event: params.meta {chat_id: owner, message_id: cron-<slug>-<id>-<slot>, ritual: cron, job: id}; content «[⏰ расписание] <id>»;
- watchdog: a job fired twice without a `done` after the first of them → one line in <state>/watch.jsonl (Quality reads it).
State lives OUTSIDE the home (<state>/<slug>.json, journal fired.jsonl). Run as root over a home: every file in the home is
opened component by component without following links (openat), must be a regular file; the journal is only appended to, never created.
Only stdlib + cronspec from skills/raspisanie."""
import argparse, datetime as dt, json, os, re, stat, sys, zoneinfo
# the command in the event — the full path: mila-cron is not on PATH in images, a Mila that sees «mila-cron» may decide the tool is missing
MC = "python3 ~/.claude/skills/raspisanie/mila_cron.py"

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, "..", "skills", "raspisanie"), os.path.expanduser("~/.claude/skills/raspisanie")):
    if os.path.isfile(os.path.join(p, "cronspec.py")):
        sys.path.insert(0, p); break
import cronspec as C

MAXF = 512 * 1024


def open_in_home(home, rel, flags):
    """Open home/rel walking it one component at a time (openat, O_NOFOLLOW on every step): no symlink anywhere on the way,
    and no window between a path check and the open — a folder swapped for a link mid-way is refused."""
    parts = [x for x in rel.split("/") if x]
    if not parts or any(x in (".", "..") for x in parts):
        raise OSError("bad path")
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nfd
        return os.open(parts[-1], flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def read_in_home(home, rel):
    """Text of home/rel: no symlink anywhere on the way, regular file, ≤ 512 KB. None if absent or refused."""
    try:
        fd = open_in_home(home, rel, os.O_RDONLY)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAXF:
            return None
        with os.fdopen(os.dup(fd), "rb") as f:
            return f.read().decode("utf-8", "replace")
    finally:
        os.close(fd)


def append_in_home(home, rel, line):
    fd = open_in_home(home, rel, os.O_WRONLY | os.O_APPEND)   # no O_CREAT: the plugin owns this file
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def user_md(home):
    t = read_in_home(home, "work/USER.md") or ""
    m = re.search(r"Часовой пояс\s*[—-]\s*([A-Za-z_]+/[A-Za-z_]+)", t)
    try:
        tz = zoneinfo.ZoneInfo(m.group(1)) if m else zoneinfo.ZoneInfo("Asia/Tashkent")
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("Asia/Tashkent")
    q = re.search(r"Тихие часы\s*[—-]\s*(\d{1,2})(?::\d\d)?\s*[–-]\s*(\d{1,2})", t)
    return tz, ((int(q.group(1)), int(q.group(2))) if q else (22, 8))


def in_quiet(t, quiet):
    a, b = quiet
    return (a <= t.hour or t.hour < b) if a > b else (a <= t.hour < b)


def quiet_end(t, quiet):
    end = t.replace(hour=quiet[1], minute=0, second=0, microsecond=0)
    return end if end > t else end + dt.timedelta(days=1)


def owner_of(home, given):
    if given:
        return str(given)
    a = read_in_home(home, ".claude/channels/telegram/access.json")
    try:
        return str((json.loads(a or "{}").get("allowFrom") or [""])[0])
    except ValueError:
        return ""


def load_state(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {"jobs": {}}


def save_state(path, s):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)
    os.replace(tmp, path)


def dones(home):
    out = {}
    for line in (read_in_home(home, "work/schedule/done.jsonl") or "").splitlines():
        try:
            r = json.loads(line); out.setdefault(r["id"], []).append(r["at"])
        except (ValueError, KeyError, TypeError):
            pass
    return out


def event(slug, owner, jid, slot, content, now):
    return json.dumps({"ts": int(now.timestamp() * 1000), "method": "notifications/claude/channel",
                       "params": {"content": content, "meta": {"chat_id": owner, "chat_type": "private",
                                                               "message_id": "cron-%s-%s-%s" % (slug, jid, slot.strftime("%Y%m%d%H%M")),
                                                               "user": "Расписание", "user_id": owner, "ts": now.isoformat(), "ritual": "cron", "job": jid}}},
                      ensure_ascii=False)


def default_state():
    """Where the Scheduler keeps its per-home state when BARABAN_STATE is not set: the XDG state folder of whoever runs it."""
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "mila", "baraban")


def tick(home, slug, owner="", state_dir=None, now=None):
    state_dir = state_dir or default_state()
    home = os.path.realpath(home)
    tz, quiet = user_md(home)
    now = (now or dt.datetime.now(tz)).astimezone(tz)
    owner = owner_of(home, owner)
    raw = read_in_home(home, "work/schedule/jobs.json")
    if raw is None or not owner:
        return {"fired": [], "why": "no jobs.json" if raw is None else "no owner"}
    try:
        jobs = [j for j in (json.loads(raw).get("jobs") or []) if isinstance(j, dict)]
    except ValueError:
        return {"fired": [], "why": "jobs.json unreadable"}
    sp = os.path.join(state_dir, "%s.json" % slug); st = load_state(sp); fired = []
    done = dones(home)
    for j in jobs:
        jid = str(j.get("id") or "")
        if not re.fullmatch(r"[a-z0-9-]{1,40}", jid) or not j.get("enabled", True):
            continue
        js = st["jobs"].setdefault(jid, {})
        exp = j.get("expires")
        if exp and now.date() > dt.date.fromisoformat(exp):
            if not js.get("expired_told"):
                fired.append((jid, now, "[⏰ расписание] %s — срок задачи вышел %s. Продлить? %s extend %s ГГГГ-ММ-ДД, или rm." % (jid, exp, MC, jid), "expired"))
            continue
        try:
            spec = C.parse(str(j.get("cron") or ""))
        except Exception:
            continue
        created = dt.datetime.fromisoformat(j["created"]).astimezone(tz) if j.get("created") else now
        last = dt.datetime.fromisoformat(js["last"]).astimezone(tz) if js.get("last") else created
        slot = js.get("waiting") and dt.datetime.fromisoformat(js["waiting"]).astimezone(tz) or spec.last_at_or_before(now)
        if not slot or slot <= last:
            continue
        if j.get("catchup") == "skip" and (now - slot) > dt.timedelta(minutes=5) and not js.get("waiting"):
            js["last"] = slot.isoformat(); continue
        if j.get("quiet", "respect") == "respect" and in_quiet(now, quiet):
            js["waiting"] = slot.isoformat(); continue          # fires once when the quiet hours end
        fired.append((jid, slot, "[⏰ расписание] %s\n%s\nСделай и запиши итог: %s done %s \"…\"" % (jid, str(j.get("text") or "")[:2000], MC, jid), "slot"))
    out = []
    for jid, slot, content, kind in fired:
        try:
            append_in_home(home, ".claude/channels/telegram/inbound/events.jsonl", event(slug, owner, jid, slot, content, now))
        except OSError as e:                                  # not delivered → state unchanged, the next minute tries again
            sys.stderr.write("baraban: %s/%s not delivered: %s\n" % (slug, jid, e)); continue
        out.append(jid); js = st["jobs"][jid]
        if kind == "expired":
            js["expired_told"] = True; continue
        js.pop("waiting", None); js["last"] = slot.isoformat()
        hist = js.setdefault("fires", []); hist.append(slot.isoformat()); del hist[:-5]
        ds = [dt.datetime.fromisoformat(x).astimezone(tz) for x in done.get(jid, [])]
        if len(hist) >= 2 and not any(d >= dt.datetime.fromisoformat(hist[-2]).astimezone(tz) for d in ds) and js.get("watched") != hist[-2]:
            js["watched"] = hist[-2]
            os.makedirs(state_dir, mode=0o700, exist_ok=True)
            with open(os.path.join(state_dir, "watch.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": now.isoformat(), "slug": slug, "job": jid, "why": "fired twice without done"}, ensure_ascii=False) + "\n")
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    if out:
        with open(os.path.join(state_dir, "fired.jsonl"), "a", encoding="utf-8") as f:
            for jid in out:
                f.write(json.dumps({"at": now.isoformat(), "slug": slug, "job": jid}, ensure_ascii=False) + "\n")
    save_state(sp, st)
    return {"fired": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scheduler: deliver mila-cron jobs as events")
    ap.add_argument("cmd", choices=("tick", "status"))
    ap.add_argument("--home", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--owner", default="")
    ap.add_argument("--state", default=os.environ.get("BARABAN_STATE") or default_state())
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    slug = a.slug or os.path.basename(os.path.realpath(a.home).rstrip("/"))
    if a.cmd == "status":
        print(json.dumps(load_state(os.path.join(a.state, "%s.json" % slug)), ensure_ascii=False, indent=1)); return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else None
    print(json.dumps(tick(a.home, slug, a.owner, a.state, now), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
