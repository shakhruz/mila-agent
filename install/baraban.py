#!/usr/bin/env python3
"""The Scheduler (RU: «Планировщик»; the file and the state keep the old name, baraban) — the schedule service outside the Claude Code session. Jobs a Mila set with mila-cron (~/work/schedule/jobs.json)
reach her as events in the plugin's journal, the same way rituals and ticks do; a session restart loses nothing.

  baraban.py tick --home H [--slug S] [--owner ID] [--state DIR] [--beat-dir DIR] [--now ISO]   # one pass; a timer runs it every minute
                                                              # no --owner: the paired owner of the home (access.json)
  baraban.py status --home H [--state DIR]                                    # jobs, last fire, last done, overdue
Rules (the same contract mila-cron and its skill describe):
- a job fires when its cron slot (in the owner's time zone, USER.md «Часовой пояс — …», else Asia/Tashkent) is newer than the
  last fire and newer than the job's creation; several missed slots → ONE event (catchup «one»), or none if catchup «skip»
  and the slot is older than 5 minutes;
- quiet hours (USER.md «Тихие часы — 22:00–08:00», else 22–08) and quiet «respect»: the slot waits until the quiet hours end
  and then fires once;
- expired job: one event «продлить?» and silence after it;
- event: params.meta {chat_id: owner, message_id: cron-<slug>-<id>-<slot>, ritual: cron, job: id}; content «[⏰ расписание] <id>»;
- watchdog: a job fired twice without a `done` after the first of them → one line in <state>/watch.jsonl (Quality reads it);
- every pass that has an owner to deliver to leaves <state>/<slug>.beat (or --beat-dir) with the time of the pass: the send guard
  lets «it stands in the Scheduler» through only while this file is fresh, and the doctor shows a Scheduler that stopped.
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
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAXF or st.st_nlink != 1:   # жёсткая ссылка на чужой файл — отказ
            return None
        with os.fdopen(os.dup(fd), "rb") as f:
            return f.read().decode("utf-8", "replace")
    finally:
        os.close(fd)


def append_in_home(home, rel, line):
    fd = open_in_home(home, rel, os.O_WRONLY | os.O_APPEND)   # no O_CREAT: the plugin owns this file
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:      # a second name (hard link) may be a file outside the home
            raise OSError("not a regular file with one name")
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def user_md(home):
    t = read_in_home(home, "work/USER.md") or ""
    tz = C.owner_tz(t)      # one rule with mila-cron and the send guard
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


def write_beat(beat_dir, slug, now, public=False):
    """«I passed for this home at …» — one small file per home. The send guard and the doctor read it: a job in jobs.json is
    a promise only while the service is passing. In the state folder (the default) it is as closed as the state; a separate
    --beat-dir is made readable for the homes' users (755, the file 644) — the state itself stays closed."""
    if not os.path.isdir(beat_dir):
        os.makedirs(beat_dir, mode=0o755 if public else 0o700, exist_ok=True)
        if public: os.chmod(beat_dir, 0o755)
    p = os.path.join(beat_dir, "%s.beat" % slug); tmp = p + ".tmp"; mode = 0o644 if public else 0o600
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with open(fd, "w", encoding="utf-8") as f:
        os.fchmod(fd, mode)
        f.write(now.isoformat(timespec="seconds") + "\n")
    os.replace(tmp, p)


def dones(home):
    out = {}
    for line in (read_in_home(home, "work/schedule/done.jsonl") or "").splitlines():
        try:
            r = json.loads(line)
            if r.get("status", "done") in ("done", "fail"):        # «start» — задача в работе, ещё не итог
                out.setdefault(r["id"], []).append(r["at"])
        except (ValueError, KeyError, TypeError):
            pass
    return out


def event(slug, owner, jid, slot, content, now):
    return json.dumps({"ts": int(now.timestamp() * 1000), "method": "notifications/claude/channel",
                       "params": {"content": content, "meta": {"chat_id": owner, "chat_type": "private",
                                                               "message_id": "cron-%s-%s-%s" % (slug, jid, slot.strftime("%Y%m%d%H%M")),
                                                               "user": "Расписание", "user_id": owner, "ts": now.isoformat(), "ritual": "cron", "job": jid}}},
                      ensure_ascii=False)


DLIT_MIN = 120                           # срок на исполнение по умолчанию (поле задачи dlit, минуты, 10…1440)
ONCE_WAIT = dt.timedelta(hours=2)        # разовое дело без итога за 2 ч → строка сторожа
FIRES_PER_DAY = int(os.environ.get("MILA_FIRES_PER_DAY") or 300)   # бюджет срабатываний своих задач в сутки на дом
OWNER_FIRES_PER_DAY = int(os.environ.get("MILA_OWNER_FIRES_PER_DAY") or 300)   # отдельный потолок задач хозяина/старшей


def watch(state_dir, now, slug, jid, why):
    """Строка сторожа исполнения: <state>/watch.jsonl (читают Качество, «Проблемы» и утренний журнал)."""
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    with open(os.path.join(state_dir, "watch.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(), "slug": slug, "job": jid, "why": why}, ensure_ascii=False) + "\n")


def _items(raw):
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else (v.get("items") or [])
    except ValueError:
        out = []
        for line in raw.splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


def run_check(home, check, now, tz):
    """«Удар» без модели (бывший Пульс, слит 15.11.2026): только встроенные проверки по данным дома, никаких команд из jobs.json —
    служба идёт под root. Возвращает [(ключ, строка)]; пусто — будить Милу незачем.
      deadlines:<файл>[:часы] — открытые пункты {id, text, due, done} со сроком в ближайшие N ч (2 по умолчанию) или просроченные;
      changed:<файл>          — файл изменился с прошлой проверки (ключ — отпечаток содержимого)."""
    kind, _, rest = str(check).partition(":")
    rel, _, arg = rest.partition(":")
    raw = read_in_home(home, rel)
    if raw is None:
        return []
    if kind == "changed":
        import hashlib
        return [("changed:" + hashlib.sha256(raw.encode()).hexdigest()[:16], "изменился %s" % rel)]
    if kind != "deadlines":
        return []
    try:
        hours = float(arg or 2)
    except ValueError:
        hours = 2
    out = []
    for it in _items(raw):
        if not isinstance(it, dict) or it.get("done") or not it.get("due"):
            continue
        try:
            due = dt.datetime.fromisoformat(str(it["due"]).replace(" ", "T"))
        except ValueError:
            continue
        due = due.replace(tzinfo=tz) if due.tzinfo is None else due.astimezone(tz)
        if due - now <= dt.timedelta(hours=hours):
            out.append(("%s:%s" % (it.get("id"), due.isoformat(timespec="minutes")),
                        "%s · срок %s%s" % (str(it.get("text") or it.get("id"))[:200], due.strftime("%d.%m %H:%M"), " · просрочено" if due < now else "")))
    return out


def default_state():
    """Where the Scheduler keeps its per-home state when BARABAN_STATE is not set: the XDG state folder of whoever runs it."""
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "mila", "baraban")


def tick(home, slug, owner="", state_dir=None, now=None, beat_dir=None):
    state_dir = state_dir or default_state()
    home = os.path.realpath(home)
    tz, quiet = user_md(home)
    now = (now or dt.datetime.now(tz)).astimezone(tz)
    owner = owner_of(home, owner)
    if owner:                                                  # no owner — nobody to deliver to: this is not a pass
        try: write_beat(beat_dir or state_dir, slug, now, public=bool(beat_dir))
        except OSError as e: sys.stderr.write("baraban: beat not written: %s\n" % e)
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
        lastfire = (js.get("fires") or [None])[-1]                # v4: сторож итога — у каждого срабатывания свой срок на исполнение
        if lastfire and js.get("late") != lastfire:
            lf = dt.datetime.fromisoformat(lastfire).astimezone(tz)
            try:
                dl = max(10, min(int(j.get("dlit") or DLIT_MIN), 1440))
            except (TypeError, ValueError):
                dl = DLIT_MIN
            if now - lf > dt.timedelta(minutes=dl) and not any(dt.datetime.fromisoformat(x).astimezone(tz) >= lf for x in done.get(jid, [])):
                js["late"] = lastfire; watch(state_dir, now, slug, jid, "no done %d min after fire %s" % (dl, lastfire[:16]))
        exp = j.get("expires")
        if exp and now.date() > dt.date.fromisoformat(exp):
            if j.get("at"):                                   # разовое отжило своё — без «продлить?», тихо
                continue
            if not js.get("expired_told"):
                fired.append((jid, now, "[⏰ расписание] %s — срок задачи вышел %s. Продлить? %s extend %s ГГГГ-ММ-ДД, или rm." % (jid, exp, MC, jid), "expired"))
            continue
        created = dt.datetime.fromisoformat(j["created"]).astimezone(tz) if j.get("created") else now
        last = dt.datetime.fromisoformat(js["last"]).astimezone(tz) if js.get("last") else created
        if j.get("at"):                                       # v4: разовое дело на дату — один раз, потом только сторож итога
            try:
                at = dt.datetime.fromisoformat(j["at"]).astimezone(tz)
            except ValueError:
                continue
            if js.get("once"):
                if not js.get("once_watched") and now - at > ONCE_WAIT and not any(
                        dt.datetime.fromisoformat(x).astimezone(tz) >= at for x in done.get(jid, [])):
                    js["once_watched"] = True; watch(state_dir, now, slug, jid, "one-off fired, no done in 2 h")
                continue
            slot = js.get("waiting") and dt.datetime.fromisoformat(js["waiting"]).astimezone(tz) or (at if at <= now else None)
        else:
            try:
                spec = C.parse(str(j.get("cron") or ""))
            except Exception:
                continue
            slot = js.get("waiting") and dt.datetime.fromisoformat(js["waiting"]).astimezone(tz) or spec.last_at_or_before(now)
        if not slot or slot <= last:
            continue
        if j.get("catchup") == "skip" and (now - slot) > dt.timedelta(minutes=5) and not js.get("waiting"):
            js["last"] = slot.isoformat(); continue
        if j.get("quiet", "respect") == "respect" and in_quiet(now, quiet):
            js["waiting"] = slot.isoformat(); continue          # fires once when the quiet hours end
        found = None
        if j.get("check"):                                      # v4: сначала дешёвая проверка; нечего делать — тихо, модель не будим
            seen = js.setdefault("seen", [])
            found = [(k, t) for k, t in run_check(home, j["check"], now, tz) if k not in seen]
            if not found:
                js["last"] = slot.isoformat(); js.pop("waiting", None); js["idle"] = js.get("idle", 0) + 1; continue
        day = now.date().isoformat()                            # v4: бюджет срабатываний в сутки на дом — держит расход, а не число задач
        if st.setdefault("day", {}).get("date") != day:
            st["day"] = {"date": day, "n": 0}
        pool = "mila" if j.get("by", "mila") == "mila" else "owner"   # бюджет на все задачи: пометка «чья задача» проверяется только по виду
        cap = FIRES_PER_DAY if pool == "mila" else OWNER_FIRES_PER_DAY  # у задач хозяина и старшей свой потолок
        if st["day"].get(pool, 0) >= cap:
            if not st["day"].get("told_" + pool):
                st["day"]["told_" + pool] = True
                watch(state_dir, now, slug, jid, "daily fire budget %d reached for %s jobs; they wait till tomorrow" % (cap, pool))
            continue
        st["day"][pool] = st["day"].get(pool, 0) + 1; st["day"]["n"] += 1
        extra = ("\nНашла проверка:\n" + "\n".join("• " + t for _, t in found[:20])) if found else ""
        fired.append((jid, slot, "[⏰ расписание] %s\n%s%s\nСделай и запиши итог: %s done %s \"…\"" % (jid, str(j.get("text") or "")[:2000], extra, MC, jid), "slot"))
        if found:
            js["_found"] = [k for k, _ in found]
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
        if js.get("_found"):
            js["seen"] = (js.get("seen", []) + js.pop("_found"))[-200:]
        if dict((x.get("id"), x) for x in jobs).get(jid, {}).get("at"):
            js["once"] = True
        hist = js.setdefault("fires", []); hist.append(slot.isoformat()); del hist[:-5]
        ds = [dt.datetime.fromisoformat(x).astimezone(tz) for x in done.get(jid, [])]
        if len(hist) >= 2 and not any(d >= dt.datetime.fromisoformat(hist[-2]).astimezone(tz) for d in ds) and js.get("watched") != hist[-2]:
            js["watched"] = hist[-2]
            watch(state_dir, now, slug, jid, "fired twice without done")
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
    ap.add_argument("--beat-dir", help="where to put <slug>.beat (default: the state folder); a root-run service points it at a folder the home's user can read")
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    slug = a.slug or os.path.basename(os.path.realpath(a.home).rstrip("/"))
    if a.cmd == "status":
        print(json.dumps(load_state(os.path.join(a.state, "%s.json" % slug)), ensure_ascii=False, indent=1)); return 0
    now = dt.datetime.fromisoformat(a.now) if a.now else None
    print(json.dumps(tick(a.home, slug, a.owner, a.state, now, a.beat_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
