# The Scheduler — jobs on time, outside the session

*Русский — [SCHEDULER.ru.md](SCHEDULER.ru.md).*

**What it is.** «Remind me every Monday», «check in a week», «send the summary at nine» — Mila writes such a job into a file in her home, and a small service outside the Claude Code session delivers it to her at the right minute as an ordinary event. A session restart, an image update or a week of silence loses nothing.

In texts for people the service is called the Scheduler (RU: «Планировщик»). File names and state paths keep the older name: `install/baraban.py`, `state/baraban`.

## Why not the session's own timer
A job set inside the session (`CronCreate`) lives in the session: it dies on restart and by itself after 7 days. A job of the Scheduler lives in `~/work/schedule/jobs.json` and is fired by a process that does not depend on the session.

## Setting a job
Mila does it with `skills/raspisanie/mila_cron.py` (the skill `raspisanie`):

```bash
M=~/.claude/skills/raspisanie/mila_cron.py
python3 $M next "0 9 * * 1" 3                    # look at the nearest slots first
python3 $M add otchet-pn "0 9 * * 1" "Monday: the weekly report to the owner"
python3 $M list                                  # next slot, last fire, last result
python3 $M done otchet-pn "sent, 5 lines"        # the result of the last fire
python3 $M pause|resume|rm <id>
python3 $M extend <id> YYYY-MM-DD
```

The owner does not type these: he says «remind me on Mondays» in the chat, Mila sets the job and names the nearest slot.

## Rules
| Rule | Value |
|---|---|
| Schedule | a 5-field cron expression, in the owner's time zone |
| How often | not more often than once in 5 minutes |
| Jobs in one home | at most 30 |
| Text of a job | 1–2000 characters |
| Lifetime | 30 days by default, 90 at most; then one event «extend?» and silence. There are no jobs without an end: an eternal job spends the subscription silently |
| Whose job | Mila's own (`by mila`), or by the owner's or the administrator's word — then with `--word <chat>/<message>`. The script checks only the form of this pointer: it cannot see the chat |

The time zone and the quiet hours are read from the owner's `USER.md` (the lines «Часовой пояс — Area/City» and «Тихие часы — 22:00–08:00»). Without the lines — Asia/Tashkent and 22–08. The zone is one rule (`cronspec.owner_tz`) for the service that fires, for `mila_cron.py` that shows the slots and for the send guard that checks a promised time: «09:00» is one moment for the three. On a machine elsewhere, write the line.

## How a job reaches Mila
Once a minute the Scheduler makes one pass (`baraban.py tick`). A job fires when its slot is newer than its last fire and newer than its creation. The fire is one line appended to the Telegram plugin's inbound journal — the same road rituals and the owner's messages take — so the session sees:

```
[⏰ расписание] otchet-pn
Monday: the weekly report to the owner
Сделай и запиши итог: python3 ~/.claude/skills/raspisanie/mila_cron.py done otchet-pn "…"
```

Mila does the job and writes the result with `done`.

- **Missed slots.** The machine was off for three slots — Mila gets ONE event, not three (`--catchup one`, the default). With `--catchup skip` a slot older than 5 minutes is dropped.
- **Quiet hours.** A slot inside the owner's quiet hours waits and fires once when they end (`--quiet respect`, the default; `--quiet ignore` fires at once).
- **Not delivered.** If the event could not be written, nothing is marked as fired: the next minute tries again.
- **Expired.** One event «the job's term is over — extend?», then silence until `extend` or `rm`.

## Watching it
- `python3 install/baraban.py status --home <home> [--state <dir>]` — per job: the last fire, the last five fires, what is waiting for the end of quiet hours.
- `<state>/fired.jsonl` — every delivered fire: time, home, job.
- `<state>/<home>.beat` — the time of the last pass for this home (every pass that has an owner to deliver to leaves it). The send guard lets «it stands in the Scheduler» through only while this mark is fresher than five minutes; `doctor` shows «jobs set, the service is not passing».
- `<state>/watch.jsonl` — a job that fired twice with no `done` after the first of the two: one line. A job that fires and is never finished is visible, not silent.

## Where it runs
- **The container image** (`docker/entrypoint.sh`): a loop runs the tick every minute for the home in the container; state in `~/state/baraban`. Nothing to set up beyond the owner: the pass runs once the owner is known (`OWNER_ID`, the paired owner) and is silent until then.
- **A server with several homes**: a timer of the machine runs `baraban.py tick --home <home> --slug <name> --owner <id> --state <dir>` once a minute, one line per home. The state folder is closed to the homes; `--beat-dir <dir>` puts the pass marks into a folder the homes' users can read (the guard looks in `/run/mila/scheduler` and in the folder named by `MILA_SCHEDULER_BEAT`).
- **A laptop** (`install/install.sh`): the installer sets a pass every minute — launchd `com.milagpt.scheduler` on macOS, a systemd user timer `mila-scheduler` on Linux; state in `~/.local/state/mila/baraban`. A home installed before this had no timer: jobs were stored and did not fire — run the installer again; `doctor` shows a Scheduler that is not passing.

## What protects the home
The service may run as root over a home it does not trust. It opens every file inside the home one path component at a time without following links, accepts regular files only, appends to the journal and never creates it, and keeps its own state outside the home — a job cannot rewrite when it last fired.

## In the code
| Part | File | Test |
|---|---|---|
| Jobs: add, list, done, extend | `skills/raspisanie/mila_cron.py`, `cronspec.py` | `skills/raspisanie/test_mila_cron.py` |
| The pass once a minute | `install/baraban.py` | `install/test_baraban.py` |
| The loop in the image | `docker/entrypoint.sh` | `docker/test_docker_files.sh` |

See also: [Concepts — who decides](CONCEPTS.md), [what Mila can do](WHAT-MILA-CAN.md).
