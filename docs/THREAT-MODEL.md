# Threat model

Mila is a Claude Code session that reads Telegram and can act: it has shell, files, and tools that write to the outside world.
This page says who can reach that session, what it can do, and where the real limits are — so you can judge the risk before you
connect a bot to it.

## Who can write to the session

| Source | How it reaches Mila | Default |
|---|---|---|
| The owner | Private chat with the bot, after pairing (`/mila-telegram:access pair <code>`) | allowed |
| People the owner allowed | `allowFrom` in `access.json` | only those listed |
| Groups the owner connected | `groups` in `access.json`, mode «Run the chat», «By mention», «Observer» or «Only me» (older groups may still be «Listen only») | only connected groups; in «Run the chat» and «Observer» the session gets every member's text; in «By mention» only messages addressed to the bot; in «Only me» only the owners' |
| Strangers in a private chat | Anyone who finds the bot | `dmPolicy: pairing` (default): the bot answers with a 6-character pairing code (at most 3 pending, the code repeated at most twice); the session never sees them until the owner approves the code. `allowlist`: dropped; with `strangerGreeting` they get a static greeting |
| Guests of a public bot (optional) | A separate guest circuit with its own prompt and settings | off unless configured |
| Forwarded text, files, links | Arrive inside an allowed message | treated as data |

Everything an allowed person writes becomes text in the session. **That text is untrusted input**: a client, a group member, or a
forwarded message may contain «ignore your rules and…». Mila's skills and the constitution tell her that instructions inside
messages from anyone but the owner, and inside forwarded or quoted text, are data, not orders. That is a behavioural defence and it
can fail. The limits below do not depend on the model behaving.

## What else the session reads — also untrusted

Text is not the only way in. Everything below is data, not orders, and the same behavioural defence (which can fail) applies:

- **Attachments** — photos, PDFs, documents, voice and video notes (voice is transcribed into text). The plugin saves them to
  the session's inbox folder; file names and captions arrive as text.
- **Links** the session opens or fetches, and web search results: the page content enters the conversation.
- **Mail** read by a mail skill, and replies to Mila's own letters.
- **The owner's personal Telegram** (opt-in add-on, below): other people's messages in his chats.
- **Files from other people's systems** — exports, spreadsheets, archives a person sends to be processed.

## What the session can do

Shell and files of its own OS user; Telegram replies through the plugin; skills that call outside services (mail, publishing,
image and voice generation, payment links). Keys for those services are the main prize for a prompt injection.

## Where the limits are

1. **Who may write at all** — pairing and the allowlist (plugin). An unknown person never reaches the session.
2. **Permission prompts** (on a laptop; off in the container, see below) — `install/permission_policy.ts` with `default: ask`:
   rules decide routine tools, anything else asks the owner on a card with a deadline; a broken policy file turns everything into
   `ask`, never `allow`; a storm limit stops card floods. The owner's press is not written to the decision log yet.
   The policy is evaluated in the plugin (the `mila-telegram` repository), the rules live here.
3. **Outward actions in the cloud — the consent proxy** (`consent/`; in the code, not installed by `install.sh` or the image yet;
   one category — publishing). The keys of
   consent categories live only with a separate OS user (`mila-io`); the session asks the proxy, the proxy shows the owner a card it signs itself, and executes only with a fresh,
   single-use consent for the hash of that exact payload (text, targets, attachment contents). A changed text or a swapped file
   needs a new yes. Unclear input, a silent proxy, a forged or foreign button — no action.
4. **The send-guard** (`templates/home/.claude/hooks/send-guard.py`) — a safety net for the model's mistakes (a reply to a chat that
   was not connected, a key in the text or in an attached file, a file outside the home or one of the agent's own key and settings
   files, another client's matters, server paths). It fails closed — with no owner id and an unreadable `access.json` nothing goes
   out — but it is pattern matching and not a boundary against a hostile sender. It hangs on the plugin's `reply` and
   `edit_message` only: a broadcast from the owner's bot (`bot-send`), a post or a mail through a service goes through other layers
   (the permission policy for the command, the skill's own card, the consent proxy where it is set up).
5. **Secrets out of the chat** — keys never pass through the conversation: the bot token is in `~/.claude/channels/telegram/.env`
   (600); service keys are entered by the owner through the safe page (`tools/seif`) straight into a 600 file; `mila export`
   refuses to pack anything its secret scanner finds. Out of the chat is not out of reach: under the same OS user the session
   can read these files (see «Same-user setups»).

## Which layer stops what

| Action | What stops a wrong one | On a laptop (one OS user) |
|---|---|---|
| A stranger writes to the bot | pairing / allowlist in the plugin — the session never sees them | same |
| A reply to a chat that was not connected | the plugin refuses an unknown `chat_id`; the send-guard blocks it too | same |
| A reply in a connected chat | the send-guard (patterns: keys, server paths, another client's matters) — a safety net only; ordinary replies go without asking | same |
| A shell command, a file edit, a tool call | the permission policy: a rule allows routine ones, anything else asks the owner on a card | same |
| A post through a consent category (publishing today) | cloud, rolling out: the consent proxy — a fresh single-use yes for that exact payload | a skill with a key in reach: only the permission policy for its command |
| A mail, a broadcast, any other service call | the skill asks the owner — behavioural, not a boundary; the permission policy for the command | same |
| Reading a key file | cloud, rolling out: consent-category keys (publishing) belong to `mila-io`, the session cannot read them; every other key — same as a laptop | nothing: the session can read it |
| Spending above a limit | the `spend` skill (pack «Images and paid generations») asks the owner on a card — behavioural: the session could call a service around it | same |
| Writing in the owner's personal Telegram | the client allows only read, draft, folder and reaction requests — not a boundary | same |

## Where secrets live

| Secret | File | Who can read it |
|---|---|---|
| Telegram bot token | Mila Agent: the key keeper (`/var/lib/mila/keys`, user `mila-keys`); elsewhere `~/.claude/channels/telegram/.env` (600) | Mila Agent: the keeper's user; elsewhere the session's OS user |
| Texts of outgoing messages on their way to the archive (Mila Agent) | `/run/mila-keyd/out/` in memory, a file per send, until the receiver takes it (every five seconds) | the keeper's and the receiver's users; not the session |
| Keys the owner typed on the safe page | `~/work/secrets/<name>.env` (600) | the session's OS user |
| Publishing key (e.g. Zernio) in the cloud setup, rolling out | consent proxy state (`mila-io`) | only `mila-io` |
| Mail, image, voice and other service keys (laptop and cloud) | `~/work/secrets/…` or the skill's environment | the session's OS user |
| The owner's Telegram user session (add-on) | `~/work/secrets/owner-tg/` (700) | the session's OS user — full access to that account |
| The owner's Claude sign-in | Claude Code's own credentials store | the session's OS user |

## Known gaps — said plainly

- **Same-user setups.** If the session and the keys live under one OS user (a laptop install), the session can read the keys and
  act without the proxy. The consent proxy is a real boundary only with the separate `mila-io` user (cloud setup).
- **«Answer everyone» and «read only» groups.** Every message of every member reaches the session. Use them only where you trust everyone.
- **A wrong pairing approval.** The owner who approves a code that a stranger sent lets that stranger write to the session. Approve
  only a code you asked someone to send; after setup switch to `/mila-telegram:access policy allowlist`.
- **Shturman — the owner's personal account in the core** (`skills/shturman`, shipped with every Mila, off until the owner signs in
  himself in a terminal). What is true of it:
  - The session file (`~/.mila-auth/shturman/`) is full access to the account. The skill's code has no sending, deleting, editing,
    reactions or «mark as read», and reaches the client through a closed list of reading calls — that guards against a mistake of
    the model, it is **not a boundary**: whoever gets the file can read and write as the owner.
  - On a laptop the session of Mila and the session file belong to the same OS user. The folder is a key place: secret-guard refuses
    Read, Grep and shell commands that name it — but code run in the shell that hides the path can still reach the file. The owner is told this in one line before he connects, and presses «yes».
  - **Injection through what is read.** A post in a channel is a stranger's text. It comes out between one-time marks and the skill
    says «data, not instructions», but that is behaviour, not a wall: a crafted post may try to talk the model into fetching the
    session file. The key guard stops the plain attempts (a test keeps a canary); the rest is this residual risk.
  - Personal chats and private groups hold other people's words — those people gave no consent. They are read only when the owner
    opened that chat himself (his own message, read from his account, fresh, used once); the rest shows as a number. Channels and
    public groups are read without a list. What Mila reads is in the Claude Code transcript (`~/.claude/projects/`); the skill's
    own journal keeps no text and no names.
  - Telegram may restrict an account driven by a program. The skill paces itself (a pause, a ceiling per hour, never the whole
    dialog list at once); the risk stays, and the owner is told.
  - What comes out of the client wrapper is plain functions and plain data: no bound method, no library object, nothing with a
    client behind it. Reaching the client through a closure (`__closure__`) needs one's own Python code in the same process — no
    new way in, and again not a boundary. The other files in the key folder (a session kept aside until its sign-out is
    confirmed, the call counter) are the same residual as the session file: a shell command with a globbed path reaches them.
  - A chat is opened only by the owner's «yes» given as a reply to Mila's exact question about that chat (the name comes from his
    account, the chat's id is in the text); the bot it is asked in is named in a file his sign-in wrote, not in the environment.
    A private channel (no public name) is read without a list, like any channel: one author speaks there, not a circle of people.
  - Revoke: `shturman.py revoke` stops reading at once, signs the session out at Telegram and wipes the files. If Telegram did not
    confirm (no network), the session file is kept aside — no command reads with it — the status stays red, and every `status`
    and `revoke` tries again; the mark goes only when a check shows the session is dead, never by a typed word.
  - Names of channels in the files Mila may read back (`map.json`, `live.json`) are a stranger's text as well: cut to one line,
    invisible characters removed, the file says so. The key guard does not catch a path that is glued together or globbed in a
    shell command — the test names two such commands as «passes».
  - In the cloud (Mila Agent in a container) Shturman does not connect yet: the session file must live with the key keeper, not
    with the session — a separate step. Sending as the owner does not exist on a laptop at all: it will come only behind the
    consent proxy, where the proxy is another OS user.
- **The owner's personal Telegram add-on** (`packs/owner-telegram`, opt-in, not installed with the core): reactions and folders on
  top of reading. A user session
  (Telethon) is full access to that account even though the client allows only read, draft, folder and reaction requests: that
  list is a whitelist inside the client, not a boundary — whoever gets the session file (`~/work/secrets/owner-tg/`) can read and
  write as the owner, and the chats belong to other people too. The tool's own files keep no message text (`drafts.jsonl` holds
  chat, length and a hash), but what Mila reads is in the Claude Code transcript (`~/.claude/projects/`). Install it only
  deliberately; revoke it in Telegram → Settings → Devices and delete the folder.
- **Development channels flag.** Until the plugin is listed in Anthropic's marketplace, `mila` starts Claude Code with
  `--dangerously-load-development-channels plugin:mila-telegram@…` — see [SECURITY.md](../SECURITY.md#the-development-channels-flag).
- **Updates.** `mila update` checks the release manifest and accepts only an explicit ok, but releases are not signed yet.

## Mila in the background on a person's own computer

After birth she runs as a service of that person's user (`install/mila-run.py`): a Claude Code session without a window, fed
from Telegram. Nobody is at a screen to answer «allow?», so the fence is what is allowed beforehand.

- **Permissions are not switched off.** The session gets a short list of its own (`mila-run-settings.json`, passed with
  `--settings`): her Telegram tools, reading and writing inside her home folder `~/work` (its `.git`, `.claude` and `.mcp.json`
  are closed for writing), reading her skills and the `inbox` folder where files people send her arrive, web search. Everything
  else Claude Code refuses by itself, and she says so.
- **Bash has no rule in that list.** A hook (`run-allow.py`) allows one shape of command only: `python3` or `bash` with a
  script that, with every link resolved, lies inside `~/.claude/skills` or `~/.claude/hooks`, typed without `..`, and with
  nothing a shell would act on. A prefix rule would let `~/.claude/skills/../../work/x.py` through — a file she can write.
- **Said plainly — what this does not stop.** (1) A script of the kit does what its arguments make it do: the fence is as
  good as the kit's own scripts. (2) The Claude sign-in made from the chat is given to the session in its environment
  (Claude Code has no other way to take it), so every script the session runs can read it from its own environment; the
  secret guard stops a command that dumps the environment, not a script that reads it. (3) Allow rules the owner wrote into
  their own `~/.claude/settings.json` apply to her as well — `mila status` and her log say how many there are. (4) She runs as
  the person's user: the wall between her and the rest of the disk is this list, not the operating system. A separate user
  of the computer for her is the wall.

## The one-container setup

`docker-compose.yml` runs Mila in one container (Claude Code, the kit, the plugin). There the session runs with
`--dangerously-skip-permissions`: layer 2 (permission prompts) is off, and the boundary is the container. What holds: pairing /
allowlist and the group mode (layer 1), the key keeper below, the send-guard (layer 4), no open ports. Mount nothing into the
container you would not hand to the session.

The Claude token and the voice keys are with the key keeper (`docker/mila_keyd.py`, user `mila-keys`, `/var/lib/mila/keys` 700, outside the home): the
session reaches Anthropic, Deepgram and Groq through it at 127.0.0.1 with a placeholder and never holds a key; the entrypoint's
root step moves keys from variables and old files into it and drops them from the session's environment. Checked in CI by
`docker/wall_probe.sh` as the session's user: files, the keeper's `/proc`, `ps`, the environment, a search of the home.
Left open: the moment a key is entered (the sign-in helper, the key page and the token page run as the session's user).
The bot token goes through the keeper too (`TELEGRAM_API_ROOT`, a placeholder token everywhere in the container); outside the
container (a hosted Mila without the keeper) it stays in the plugin's `.env`, readable by the session's user. `secret-guard.py`
and the deny rules stay as the layer in front.

The receiver's journals (`inbound/events.jsonl`, `cards.jsonl`) are what the pack installer (`update.py install-pack`) and
`spend.py` check for «the owner sent this file» and «the owner pressed yes». They are written by the receiver but owned by
the session's user, so a deliberate injection can append a fake «owner» line (a real `file_id` from a group plus a fake
press). It is a lock against accidents and naive instructions, not against a deliberate attack — until the receiver runs as
its own user and signs its lines.

## Reporting

See [SECURITY.md](../SECURITY.md) — private channel, answer within 5 business days.
