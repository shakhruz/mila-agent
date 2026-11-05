# Groups: strangers stay out of the session, the team is the owner's choice

In a group Mila is connected to, people are of three kinds, decided by Telegram id — never by name:
- **owner** — `io/owners.json` in Mila Agent (see [RECEIVER-AND-JOURNALS](RECEIVER-AND-JOURNALS.md));
- **team** — people the owner added to this group's team with a button;
- **stranger** — anyone else: other members, bots, channels, anonymous admins.

Owners and the team reach the Claude session, which has all of Mila's tools. Strangers do not.

## What happens to a stranger's message

- It goes to `guests.jsonl` in the receiver's journal folder (`~/.claude/channels/telegram/io/` in Mila Agent), file mode
  0600. The session's user can read the other journals there, not this one.
- No typing indicator, no 👀, no answer, and the files they send are not downloaded.
- The session learns only how many strangers wrote since it last heard from the chat: the next message from an owner or
  the team carries `guests_since_last="N"`. The number, never the text.
- When an owner or a team member replies to a stranger's message, the session gets a placeholder instead of the quote:
  «a stranger's message, N characters — not shown to the session». The stranger's words stay in the guests' journal.
- The response mode of the group (run the chat, by mention, observer, only me) applies to owners and the team.

Answering strangers — a separate lane with no tools — is not in this version. Without it, strangers in a group get no answer.
What is already there for it: the key keeper holds a separate key for strangers (`ANTHROPIC_GUEST_API_KEY`, an Anthropic API
key — a subscription token is refused, the owner's plan is not for serving other people). Its route `/guest/v1/messages` is
open only to the lane's own OS user (uid `MILA_GUEST_UID`, 1004 by default, known on the unix socket); that user reaches
nothing else — not the owner's Claude, not Telegram, not voice.

## The team

- When a stranger first writes in a group, every owner gets a private card: «… writes in «G». Mila does not see these messages
  and does not answer. Add to this group's team?» with **Add to the team** and **Not now**. After **Add**, a **Remove from the
  team** button stays under the card.
- One card per person per group; at most 5 cards per group an hour. Bots, channels and anonymous admins get no card.
- Only an owner's press in a private chat changes the list. A press in a group, or by anyone else, is refused.
- The list lives in `team.json` in the receiver's folder. In Mila Agent the session can read it, not write it, and a `team`
  line in `access.json` (which the session can write) is not trusted. On a plain install (one OS user, no receiver folder)
  `access.json` → `groups.<id>.team` is read too, as before.
- A team member's request goes to the session like the owner's, marked `from="team"`. Steps outward, money and the owner's
  files still go by the owner's card — a rule Mila follows (`CLAUDE.md`, `cards`), not a lock in this version.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| author by id: owner / team / stranger | plugin `authorOf()` (`receiver.ts`, `server.ts`); `teamOf()` (`team.mjs`) |
| a stranger's message → `guests.jsonl` 0600, not to the session; no typing, ack, download | plugin `guestEvent()` and the branch at the start of `handleInbound()` (`receiver.ts`, `server.ts`) |
| a reply to a stranger: a placeholder, not their words | plugin `strangerQuoted()` (`receiver.ts`, `server.ts`) |
| `guests_since_last` — a number only | plugin `GUESTS_SINCE` (`receiver.ts`, `server.ts`); feeder `ATTRS` (`install/companion-feeder.py`) |
| the card, its limits, no card for bots/channels/anonymous admins | plugin `askTeam()`; `askOnce()` (`team.mjs`); strings `team.*` (`i18n.mjs`) |
| only the owner's press in a private chat changes the team | plugin callback `team:add|skip|del` (`receiver.ts`, `server.ts`); `setTeam()` (`team.mjs`) |
| in Mila Agent the team from the receiver's file only | plugin `teamOf(…, trustAccess = !TELEGRAM_JOURNAL_DIR)` |
| the strangers' key: an API key only, its route only for the lane's OS user, that user nowhere else | `docker/mila_keyd.py` (`guest` route, `GUEST_UID`, the check in `handle_any`) |
| checked | plugin `safe-route.test.ts`, `foundation.test.ts`, `i18n.test.ts`; `install/test_feeder_envelope.py`; `docker/test_mila_keyd.py` |

## Not verified live yet

- A real group with two people (the owner and a stranger) on a stand: the stranger's message not in the session, the card in
  the owner's private chat, the press, the next message in the session.

## What stays open

- A stranger's reaction (an emoji, no text) still reaches the session as before.
- An owner's forward of a stranger's message, or an owner's own quote of their words typed into a message, reaches the session:
  that is the owner's choice, the code does not cut it.
- Group response modes are still in `access.json`, which the session can write.
- The strangers' lane (answers with no tools, on an API key) — the next part of this step.
