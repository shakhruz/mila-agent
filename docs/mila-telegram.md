# Mila Telegram — the Telegram channel for Claude Code

Talk to your Claude Code session from Telegram, and keep the conversation when the session restarts. Mila Telegram is an
open plugin (Apache-2.0, a fork of Anthropic's official Telegram channel plugin); Mila Agent uses it, and it also works on its
own with a plain Claude Code.

## What it does

Checked against the plugin's code (`shakhruz/mila-telegram`, main `94bb6e2`).

- **Messages both ways.** What people write to your bot arrives in the session as `<channel …>` messages. The assistant
  answers with the `reply` tool:
  - plain text or Telegram MarkdownV2;
  - a reply to a specific message;
  - files (images as photos, the rest as documents, up to 50 MB each);
  - inline buttons — links, or choices that come back as `[button] <label>`; up to 3 per row, 6 in total.
- **Edit and react.** `edit_message` edits the bot's own message, for example «working…» → the result; edits don't ping the
  person. `react` puts an emoji reaction from Telegram's fixed list.
- **Files and voice.** Photos are downloaded as they arrive. Other files are downloaded on request with `download_attachment`
  (Telegram serves bots files up to 20 MB). Voice notes go to a transcription command you set
  (`TELEGRAM_VOICE_TRANSCRIBE_CMD`); without it the assistant gets «(voice message)».
- **A daemon that survives restarts.** Run `receiver.ts` with `RECEIVER_DAEMON=1`. It polls Telegram and writes every allowed
  message to a journal (`inbound/events.jsonl`); a restarted session reads what it missed. Without the daemon the session
  polls Telegram itself while it runs.
- **Who may write.**
  - In private chats: pairing — a stranger gets a 6-character code, you approve it in the session — and then an allowlist.
  - Groups: added by you. Add the bot to a group and a card comes to your private chat; `/channel_join` in the group is a
    fallback. You choose a mode:
    - **Run the chat** — reads everyone, replies when needed;
    - **By mention** — sees only messages addressed to it;
    - **Observer** — reads everyone for context, replies only when addressed;
    - **Only me** — only the owners can call it there.
  - Co-owners: the card goes to all of them, and the first to press decides.
- **Tool permissions from Telegram.** When Claude Code asks permission for a tool, the owner gets a card with **Allow**
  (green), **Deny** (red) and **See more**. This applies where Claude Code asks — a regular session, not one started with
  `--dangerously-skip-permissions`.
- **Its own words in your language.** Cards, button answers, pairing texts and the command menu come in English, Russian or
  Uzbek, following the person's Telegram language; English when unknown.
- **`/whoami` for anyone.** Says it is an AI, what it runs on and who is responsible for it.

## Install on a plain Claude Code

Needs [Bun](https://bun.sh) and a bot from [@BotFather](https://t.me/BotFather).

```
/plugin marketplace add shakhruz/mila-telegram
/plugin install mila-telegram@mila
/telegram:configure <your bot token>
```

Then start Claude Code with the channel flag (the plugin is not yet on Anthropic's approved list for `--channels`):

```sh
claude --dangerously-load-development-channels plugin:mila-telegram@mila
```

Write to your bot, get the pairing code, and in the session: `/telegram:access pair <code>`, then
`/telegram:access policy allowlist`.

What we checked on 5 November 2026:
- adding the marketplace and installing the plugin on a clean Claude Code 2.1.310 home (works);
- starting the plugin's server from a clean checkout with no `node_modules` (Bun fetched the dependencies; the server started
  in polling mode).

The full round trip with a real bot on a clean machine is **not verified live** for this release.

## How it works with Claude Code

- The plugin is an MCP server (`server.ts`) that Claude Code starts, plus an optional daemon (`receiver.ts`).
- Messages reach the session as channel notifications.
- The assistant answers with the plugin's tools.
- Settings and state live in `~/.claude/channels/telegram/` (or `TELEGRAM_STATE_DIR`): `access.json`, the journal,
  per-chat notes, downloaded files, and `.env` with the token (mode 600) if you saved it there.

The plugin does not need the rest of Mila. Mila Agent adds the session in a container, the key keeper (the bot token lives
outside the session), schedules and skills.

## What it does not do

- **No chat history or search.** Telegram's Bot API gives neither; the bot sees messages only as they arrive.
- **Pinning messages and forum topics:** not in the open plugin yet; planned as a separate update.
- **Telegram Business chats:** not in the open plugin.
- **Journal limits.** The journal has no size limit or expiry yet, and keeps message text as it came (keys and tokens are
  masked); downloaded files are not deleted automatically. See [PRIVACY](https://github.com/shakhruz/mila-telegram/blob/main/PRIVACY.md).
- **Voice notes are transcribed before the sender check** — also from people who are not allowed (the text is then dropped); being
  fixed.
- **Messages are untrusted input.** Someone allowed to write can try to instruct the assistant. In «Run the chat» and «Observer»
  that is every member of the group.

## Links
- Code and full setup: [github.com/shakhruz/mila-telegram](https://github.com/shakhruz/mila-telegram)
- Access and group modes: [ACCESS.md](https://github.com/shakhruz/mila-telegram/blob/main/ACCESS.md)
- Privacy: [PRIVACY.md](https://github.com/shakhruz/mila-telegram/blob/main/PRIVACY.md)
- Mila Agent: [README](../README.md)
