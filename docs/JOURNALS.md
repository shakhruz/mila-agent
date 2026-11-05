# Journals: what is written, when, and what the session gets

Every message the bot receives is written to the receiver's journal (`events.jsonl`; in Mila Agent under
`~/.claude/channels/telegram/io/`, see [RECEIVER-AND-JOURNALS](RECEIVER-AND-JOURNALS.md)). This step fixed three gaps between
what the docs said and what the code did.

## Voice is transcribed only after the access check

- A voice message is downloaded and sent to speech-to-text only once the plugin knows it is from someone allowed: the owner,
  a person on the DM list, the owner or the team in a connected group.
- A voice from someone not allowed, or from a stranger in a group, is never downloaded and never transcribed. A stranger's
  voice reaches the guests' journal as `(voice message)`.
- A voice with a caption is not transcribed at all: the caption is the text, as before.

## The journal first, the 👀 after

- The ack reaction (👀 by default) is set only after the message is written to the journal. If the journal cannot be written,
  there is no ack: the person is not told «got it» for a message nobody has.

## One envelope

- The session reads every message as a `<channel source="telegram" …>` envelope. One builder (`install/envelope.py`) makes it
  for both paths: the feeder (Mila Agent) and the `UserPromptSubmit` hook (a plain install).
- Attributes, the same on both paths: `chat_id`, `message_id`, `user`, `lang`, `ts`, `user_id`, `from` (owner / team / other),
  `type` (reaction / callback), `observe_only`, `chat_type`, `chat_title`, `guests_since_last`. Only known values go into
  attributes; everything from the chat is escaped, so a crafted text cannot close the envelope.
- The Stop hook (`reply-required.py`) reads `type` and `observe_only` from it: a reaction or an observer message does not
  demand an answer.

## Docs = code

- There is no sender daemon, no `outbox/` and no `mila say`: replies go through the plugin's `reply` tool. `mila status`
  shows the receiver, the bridge and the journal.
- `install/tg_delivery.py` keeps the core's own delivery journal; the plugin does not write it.
- `key_in_chat.py` is not on the inbound path. What keeps a key in a person's message from the model is the receiver's
  `maskSecrets`.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| voice after the gate; strangers' voice not downloaded | plugin voice handler and `textLater` in `handleInbound()` (`receiver.ts`, `server.ts`) |
| journal before the ack; no journal — no ack | plugin `handleInbound()`: `await mcp.notification`, then the ack only if `journaled` (`receiver.ts`, `server.ts`) |
| one envelope for the feeder and the hook | `install/envelope.py`; `install/companion-feeder.py`, `install/telegram-inbox-feed.py`; `install/install.sh` puts it next to the hook |
| no sender, outbox, `mila say` | `install/mila`, `skills/mila-session/mila.sh`, `skills/mila-session/SKILL.md` |
| checked | plugin `voice-gate.test.ts`, `journal-order.test.ts`; `install/test_inbox_feed_envelope.py`, `install/test_feeder_envelope.py`, `install/test_reply_required.py`, `install/test_install_hooks.sh` |

## Not verified live yet

- A voice from a stranger in a real group: no file in `inbox/`, no call to speech-to-text.

## What stays open (later, by the owner's word)

- How long journals are kept and their rotation.
- Card and phone numbers in inbound text are kept as they came (only keys are masked).
- `mila forget` / `mila export --person`.
