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

## Files (part B)

- The original of a photo (the largest size), voice, audio, video, round video, document, sticker or animation is saved under
  `archive/<chat_id>/files/<sha256[:2]>/<sha256>.<ext>`, 0600; the message's line carries `file_sha`, `file_ext`, `file_size`.
  The same file twice is stored once.
- A stranger's file is kept the same way — the owner's decision: strangers' originals, 12 months — but never transcribed and
  never shown to the session.
- Over 20 MB (what Telegram serves to a bot): the line says «not downloaded: over 20 MB», with the file id.
- A ceiling: `ARCHIVE_FILES_MB` (2000 by default), strangers' files at most half of it. Over it a file is not kept — the line says
  «not downloaded: the archive is full» — and the owner gets one line a day. The owner's private chat is not counted. (Files that
  arrive at the same moment may pass the ceiling by one.)

## Outgoing (part C)

- Every send that goes through the key keeper — `reply`, an edit, a file, a send from the shell — is in the archive too: the keeper
  copies what Telegram answered (method, chat, message id, text, file id) into a spool `/run/mila-keyd/out/` that only the
  receiver's user reads; the receiver moves it into `archive/<chat_id>/` as `from: "mila"` lines, each once. The keeper keeps
  nothing itself; the bot token never goes into the spool.

## Where it is on

Only in Mila Agent (the receiver's own folder) or with `TELEGRAM_ARCHIVE=1`. A plain install of the plugin keeps no archive and
posts nothing about one — and there, with one OS user, it would not be a wall anyway.

## People are told

- When the owner connects a group, the group gets one line: Mila keeps an archive of this chat, the owner can read it, to have
  your messages removed — ask the owner. The owner's connection card says the same.
- A group connected before the archive existed gets that line once, with its first message after the update.
- An observer group (the owner's word) is not told in the group: only the owner's connection card says it. If its mode changes
  later, it is told then.
  Since its people are not told, a stranger there is kept as metadata only — who and when (`untold: true`), no words, no file.

## Kept for how long

Texts and transcripts — for good (the owner's decision). Original files: the owner's and the team's for good, strangers' 12
months — the sweep that deletes them comes in a later part; until then they stay.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| per chat and month, 0700 folder, 0600 files, keys masked | plugin `archive()` (`receiver.ts`) |
| owner / team / stranger lines; nothing from unconnected chats | plugin `handleInbound()`, `guestEvent()` (`receiver.ts`) |
| edits as their own lines | plugin `edited_message` handler, `allowed_updates` (`receiver.ts`) |
| the group told at connection and once after the update; the owner's card | plugin `join.archive`, `join.archiveOwner` (`i18n.mjs`), `announceArchive()` (`receiver.ts`) |
| originals by content hash, strangers' without STT, over 20 MB — metadata; the ceiling | plugin `mediaOf()`, `archiveFile()`, `archiveMessage()`, `roomFor()` (`receiver.ts`); `archive.full` (`i18n.mjs`) |
| outgoing through the keeper's spool, each once | `docker/mila_keyd.py` `spool_out()`, `OUT_SPOOL`; plugin `drainOutSpool()` (`receiver.ts`); `docker/entrypoint.sh` `TELEGRAM_OUT_SPOOL` |
| checked | `docker/test_mila_keyd.py`; plugin `archive-out.test.ts`, `archive.test.ts`, `join-archive.test.ts`, `archive-files.test.ts`, `archive-cap.test.ts` |

## Not verified live yet

- A real chat over a day: the files, their modes, an edit.
- A send from the shell (`curl` through the keeper) lands in the archive as a `mila` line.

## What stays open

- Removing a person's words on request (`forget`) is not there yet — the next part; until then the notice says «ask the owner».

## Next parts

`mila recall` with an author filter · the retention sweep · backups.
