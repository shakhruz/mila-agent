# The archive: every message kept, read only by the receiver

In Mila Agent the receiver (OS user `mila-io`) keeps every message from a connected chat — the owner's private chat, the groups
the owner connected — in `~/.claude/channels/telegram/io/archive/`. The folder is 0700: the session's user cannot list or read
it. What the session may see of it comes through a search that filters by author (a later part of this step).

## What is written now (part A)

- `archive/<chat_id>/<YYYY-MM>.jsonl`, files 0600, one line per message: time, message id, author by Telegram id (`owner`,
  `team`, `other`), kind (`text`, `voice`, `photo`, …), the text as the session got it (a voice — its transcript), the file id,
  the topic. Keys in the text are masked, as in the journal.
- Strangers in a group: their lines are there too (`other`), written by the receiver; their words still never reach the
  session.
- An edit of a message is its own line (`edit: true`, the message id, the new text); the earlier text stays.
- A chat that is not connected, a DM from someone not allowed: nothing is written.

## Kept for how long

Texts and transcripts — for good (the owner's decision). Original files — the next part: the owner's and the team's for good,
strangers' 12 months.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| per chat and month, 0700 folder, 0600 files, keys masked | plugin `archive()` (`receiver.ts`) |
| owner / team / stranger lines; nothing from unconnected chats | plugin `handleInbound()`, `guestEvent()` (`receiver.ts`) |
| edits as their own lines | plugin `edited_message` handler, `allowed_updates` (`receiver.ts`) |
| checked | plugin `archive.test.ts` |

## Not verified live yet

- A real chat over a day: the files, their modes, an edit.

## Next parts

Original files and voice (strangers' without transcription, 12 months) · outgoing messages through the key keeper · `mila
recall` with an author filter · the retention sweep · backups · on a plain install (one OS user) the archive is not a wall.
