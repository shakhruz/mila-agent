# The receiver and its journals (Mila Agent)

In the Mila Agent container, the part that talks to Telegram — the receiver — runs as its own OS user, `mila-io`. What only it
may write (the inbound journal, button presses, authorizations) lives in a folder the session can read but cannot change. Every
message carries its author, decided by the Telegram id, never by a name. This is the base the group modes and the consent
proxy will stand on.

## Users in the container

| User | What runs as it | Keys | Writes |
|---|---|---|---|
| `agent` (1001) | Claude Code session, feeder, sign-in helpers, Baraban | none — goes through the key keeper with a placeholder | the home; Telegram state shared with `mila-io` (cards, notes, settings) |
| `mila-keys` (1002) | key keeper `docker/mila_keyd.py` | Claude, bot, Deepgram, Groq | `/var/lib/mila/keys` (700, outside the home) |
| `mila-io` (1003, member of group `agent`) | receiver `receiver.ts` | none — keeper over a unix socket | `~/.claude/channels/telegram/io/` (journals) and shared Telegram state |

The entrypoint's root step creates the folders and moves journals of earlier starts into `io/`. It then starts a supervisor as
`mila-io` that waits for the session's side to say «go» (`telegram/receiver.go`, written after the token page, pairing and the
Claude sign-in, which read Telegram updates themselves). After that the supervisor waits until the key keeper has the bot token (the line «mila-agent: receiver waits for the bot token in the key
keeper», once, in the platform's log and in `/run/mila-io/receiver.log`), runs the receiver and marks it as running (`/run/mila-io/receiver.up`).

## Files

`~/.claude/channels/telegram/` (group `agent`, setgid):

| File | Written by | Session (agent) |
|---|---|---|
| `io/events.jsonl` — inbound messages, reactions, presses as events | receiver | reads; cannot write (`io/` is `mila-io:agent 2750`, files 0640) |
| `io/taps.jsonl` — every button press: who, which button, the card text as Telegram showed it | receiver | reads; cannot write |
| `io/auth-log.jsonl` — group connections and their modes | receiver | reads; cannot write |
| `io/suspicious.jsonl` — forged envelopes, someone else's press | receiver | reads; cannot write |
| `io/owners.json` — who is an owner | root step from the platform's `OWNER_ID` / `OWNERS`, or the receiver once at the first «go» | reads; cannot write |
| `inbound/events.jsonl`, `taps.jsonl`, `auth-log.jsonl`, `suspicious.jsonl` | links to `io/` for older readers | — |
| `access.json`, `cards.jsonl`, `chats/`, `CHATS.md`, `langs.json`, `.env` (placeholder token) | both | reads and writes (0660) |

Where the machine has a `mila-io` user (decided by `/etc/passwd`, not by a variable the session could unset), the pack
installer (`update.py`), the spend ledger (`spend.py`) and the feeder read the receiver's files only from `io/`. They read
them only if the folder and the file belong to `mila-io` and are not links. There is no fallback to the old places. The card text in a press is the
message Telegram showed the owner, not the session's own registry. A line the session adds to `cards.jsonl` is therefore not
a press.

## Who is an owner

`io/owners.json`:
- written by the root step from the platform's `OWNER_ID` / `OWNERS` when they are set;
- otherwise written once by the receiver at the first «go» — the owner the sign-in paired, before the session ever ran.
- a home updated from a version before `mila-io` (journals in the old place, or the session's transcripts in `~/.claude/projects` —
  the session has run there and could have changed the sign-in's files): only from
  `OWNER_ID` / `OWNERS`. Until they are set, nobody counts as the owner for presses and group decisions, and the start log asks for
  `OWNER_ID`.

The receiver's `owner` mark, the pack installer and the spend ledger take owners only from it. A line the session adds to
`access.json` or `policy.json` makes nobody an owner.

## Author of every message

The receiver adds `from` to every event:
- `owner` — one of the owners (`io/owners.json`);
- `team` — listed in the group's `team` in `access.json`;
- `other` — anyone else, including bots, channels and anonymous admins.

The feeder puts it into the session's envelope as `from="…"`, together with `user_id`, `type` (reaction, callback),
`observe_only`, `chat_type` and `chat_title`. Values are checked against patterns, so a name or text cannot fake an attribute.

## Telegram updates only for the receiver

The key keeper serves the Bot API on TCP 127.0.0.1:8790 and on a unix socket `/run/mila-keyd/api.sock`. On the socket it knows
the calling OS user (`SO_PEERCRED`).
- `getUpdates` and `deleteWebhook` (reading the bot's updates) are allowed to `mila-io` over the socket.
- To anyone else they are allowed only while the receiver is not up — the sign-in helpers before the first start.
- After that the session cannot read the bot's updates — strangers' messages included — around the receiver.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| receiver as `mila-io`, after «go» | `docker/entrypoint.sh` (root step, supervisor) |
| journals in `io/`, 0640, folder 2750 `mila-io:agent` | `docker/entrypoint.sh`; plugin `TELEGRAM_JOURNAL_DIR`, `JOURNAL_MODE` (`receiver.ts`) |
| `from` by Telegram id | plugin `authorOf()` (`receiver.ts`); feeder `meta_attrs()` (`install/companion-feeder.py`) |
| presses with Telegram's card text | plugin `TAPS_FILE` (`receiver.ts`) |
| a press and the owners trusted only from `mila-io`'s files; container decided by `/etc/passwd` | `skills/mila-update/update.py` `io_uid()`, `receiver_journal()`, `owner_ids()`; `packs/kartinki/spend/spend.py` `io_file()`, `owners()`; `install/companion-feeder.py` `events_path()`; plugin `ownersOf()` |
| owners from the platform or the first «go» | `docker/entrypoint.sh` (root step, supervisor) |
| updates only for `mila-io` | `docker/mila_keyd.py` `tg_allowed()`, `ProxyUnix` |
| checked | `docker/test_mila_keyd.py`, `install/test_feeder_envelope.py`, `install/test_reply_required.py`, `skills/mila-update/test_packs.py`, `packs/kartinki/spend/test_spend_tap.py`, plugin `foundation.test.ts`; in the image build `docker/wall_probe.sh` |

## Not verified live yet

- The full start in a container with a real bot: the receiver under `mila-io`, the go step, pairing and sign-in before it.
  Checked by tests and the image build's probe, not on a live host.
- `MILA_IO=off` keeps the old way: the receiver runs as `agent`, and its journals are the session's to write.

## What stays open

- The session (`agent`) can still change `access.json` (who may write to the bot, group modes), the card registry and chat
  notes — shared on purpose (pairing, Mila's notes). It cannot make anyone an owner or a team member: the team lives in the
  receiver's `io/team.json` (see [SAFE-GROUPS](SAFE-GROUPS.md)). Group modes move to the receiver's side later.
- A co-owner added later: set `OWNERS` on the platform and restart.
- In the main session, what owners and team members write is read as usual. Strangers' raw text is kept away from the main
  session in the next step (the safe mode for groups).
