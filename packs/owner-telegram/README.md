# The owner's personal Telegram — an opt-in add-on

> **🔴 Read before installing.** This add-on gives Mila a *user session* (Telethon) of your own Telegram account. Whoever
> has that session file can read **and write** as you, in every chat — including chats that belong to other people. The
> read-only mode below is a whitelist of requests inside the client, **not a security boundary**: code running as the same
> OS user can use the session file directly. Install it only if you want this, on a machine you control.

**What it does.** Mila reads new messages in your personal Telegram, puts a draft in your voice into the input field,
reacts to a short «thanks» with an emoji you allowed, sorts chats into folders, gathers news from your channels. She never
sends, edits or deletes on your behalf — you always press send yourself.

**Where things are.**
- The session and the Telegram app keys: `~/work/secrets/owner-tg/` (folder 700, files 600). The core never carries them;
  you or your administrator create the session once.
- What the tool writes there: `drafts.jsonl` (chat, length and a hash of each draft — no text) and `allowed.json` (private
  chats you opened by your word). Message texts are not written to these files.
- What Mila reads becomes part of her conversation: Claude Code keeps the session transcript in `~/.claude/projects/`, like
  any other chat — so other people's messages she read are in that transcript. Keep the machine and that folder private.

**Turn it off.** Telegram → Settings → Devices → end the session; then delete `~/work/secrets/owner-tg/`.

**Install.** Build: `python3 tools/pack_mila.py owner-telegram`; then `bash install.sh` from the zip (puts the skill into
`~/.claude/skills/owner-telegram`, changes nothing else). Needs `pip install telethon`.
