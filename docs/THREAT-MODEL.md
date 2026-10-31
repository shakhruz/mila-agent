# Threat model

Mila is a Claude Code session that reads Telegram and can act: it has shell, files, and tools that write to the outside world.
This page says who can reach that session, what it can do, and where the real limits are — so you can judge the risk before you
connect a bot to it.

## Who can write to the session

| Source | How it reaches Mila | Default |
|---|---|---|
| The owner | Private chat with the bot, after pairing (`/mila-telegram:access pair <code>`) | allowed |
| People the owner allowed | `allowFrom` in `access.json` | only those listed |
| Groups the owner connected | `groups` in `access.json`, mode «on mention», «answer everyone» or «read only» | only connected groups; in «answer everyone» and «read only» the session gets every member's text (in «read only» it cannot answer) |
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
2. **Permission prompts** — `install/permission_policy.ts` with `default: ask`: rules decide routine tools, anything else asks the
   owner on a card with a deadline; a broken policy file turns everything into `ask`, never `allow`; a storm limit stops card floods.
   The policy is evaluated in the plugin (the `mila-telegram` repository), the rules live here.
3. **Outward actions in the cloud — the consent proxy** (`consent/`). The service keys live only with a separate OS user
   (`mila-io`); the session asks the proxy, the proxy shows the owner a card it signs itself, and executes only with a fresh,
   single-use consent for the hash of that exact payload (text, targets, attachment contents). A changed text or a swapped file
   needs a new yes. Unclear input, a silent proxy, a forged or foreign button — no action.
4. **The send-guard** (`templates/home/.claude/hooks/send-guard.py`) — a safety net for the model's mistakes (a reply to a chat that
   was not connected, a key in the text, another client's matters, server paths). It fails closed, but it is pattern matching and
   not a boundary against a hostile sender.
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
| A post, a mail, a broadcast through a service | cloud: the consent proxy — a fresh single-use yes for that exact payload | a skill with a key in reach: only the permission card for its command |
| Reading a key file | cloud: the key belongs to `mila-io`, the session cannot read it | nothing: the session can read it |
| Spending above a limit | a card with the owner's tap (`spend`), checked by the tool | same |
| Writing in the owner's personal Telegram | the client allows only read, draft, folder and reaction requests — not a boundary | same |

## Where secrets live

| Secret | File | Who can read it |
|---|---|---|
| Telegram bot token | `~/.claude/channels/telegram/.env` (600) | the session's OS user |
| Keys the owner typed on the safe page | `~/work/secrets/<name>.env` (600) | the session's OS user |
| Publishing key (e.g. Zernio) in the cloud setup | consent proxy state (`mila-io`) | only `mila-io` |
| Mail, image, voice and other service keys on a laptop | `~/work/secrets/…` or the skill's environment | the session's OS user |
| The owner's Telegram user session (add-on) | `~/work/secrets/owner-tg/` (700) | the session's OS user — full access to that account |
| The owner's Claude sign-in | Claude Code's own credentials store | the session's OS user |

## Known gaps — said plainly

- **Same-user setups.** If the session and the keys live under one OS user (a laptop install), the session can read the keys and
  act without the proxy. The consent proxy is a real boundary only with the separate `mila-io` user (cloud setup).
- **«Answer everyone» and «read only» groups.** Every message of every member reaches the session. Use them only where you trust everyone.
- **A wrong pairing approval.** The owner who approves a code that a stranger sent lets that stranger write to the session. Approve
  only a code you asked someone to send; after setup switch to `/mila-telegram:access policy allowlist`.
- **The owner's personal Telegram** (`packs/owner-telegram`, an opt-in add-on, not installed with the core). A user session
  (Telethon) is full access to that account even though the client allows only read, draft, folder and reaction requests: that
  list is a whitelist inside the client, not a boundary — whoever gets the session file (`~/work/secrets/owner-tg/`) can read and
  write as the owner, and the chats belong to other people too. The tool's own files keep no message text (`drafts.jsonl` holds
  chat, length and a hash), but what Mila reads is in the Claude Code transcript (`~/.claude/projects/`). Install it only
  deliberately; revoke it in Telegram → Settings → Devices and delete the folder.
- **Development channels flag.** Until the plugin is listed in Anthropic's marketplace, `mila` starts Claude Code with
  `--dangerously-load-development-channels plugin:mila-telegram@…` — see [SECURITY.md](../SECURITY.md#the-development-channels-flag).
- **Updates.** `mila update` checks the release manifest and accepts only an explicit ok, but releases are not signed yet.

## Reporting

See [SECURITY.md](../SECURITY.md) — private channel, answer within 5 business days.
