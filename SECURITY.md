# Security policy

Mila runs an AI agent that can read and write in Telegram chats and on a
machine, so security reports are taken seriously.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's "Report a vulnerability" (private security
advisory) on this repository, or e-mail hello@milagpt.io with "security" in the subject.
Please include what you found, how to reproduce it and the impact.
We acknowledge every report within 5 business days.

Before you connect a bot: [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) — who can write to the session, what it can do,
where the limits are and the known gaps.

## Scope

In scope: the hooks and tools in `install/` and `templates/`, the send-guard, the
installer and bootstrap scripts, secret handling in backups, access control and
pairing flow guidance.

Out of scope: vulnerabilities in Claude Code, Telegram or other upstream software
(report those to their vendors), and misconfiguration of your own server.

## The Claude token in the one-container setup

In the container (Railway, docker-compose) the Claude token and the voice keys are with the key keeper (`docker/mila_keyd.py`):
its own user (`mila-keys`), files in `~/.keys` (700) the session's user cannot read, keys from earlier starts and from platform
variables moved there by the entrypoint's root step. Claude Code and the voice script talk to the keeper at 127.0.0.1 with a
placeholder; the keeper puts the key into the request to Anthropic, Deepgram or Groq. The model can use a key, not read it:
only Mila's own calls pass (messages, speech-to-text), account, usage and key-management paths are refused before they
reach the provider, and a key already there is replaced only when the provider no longer takes it (or by a platform variable).
`docker/wall_probe.sh` (run in CI inside the image) tries the ways out as the session's user. What is still open: a key
passes through the sign-in helper or the key page (the session's user) for a moment when it is entered; the bot token is still readable by the session — it moves to the
keeper next. `MILA_KEYD=off` turns the keeper off (the old way: treat a prompt injection as able to see the token).

The receiver's journals (`inbound/events.jsonl`, `cards.jsonl`) are still the session's user's: the pack installer and the spend ledger
trust them for «the owner sent this file» and «the owner pressed yes», and they belong to the session's user. That stops an
accident or a naive instruction, not a deliberate injection that writes a fake line. The fix is the step the keys took: the receiver
as its own user, signing its lines.

## What the send-guard is — and is not

The send-guard (`templates/home/.claude/hooks/send-guard.py`, a `PreToolUse` hook on `reply`/`edit_message`) catches the
model's mistakes: a message to a chat the owner did not connect, a key or token in the text, server paths, one client's
matters in another client's chat. It fails closed by itself: if it cannot read its input or hits any error, it exits with
code 2 and a deny, so the unchecked message is not sent (the `onFailure: "block"` setting is an extra layer where Claude
Code supports it, not the only one).
It is pattern matching, so it is **not** a security boundary against a hostile sender: a determined party can split or encode
text, or use another tool. The boundaries are who may write to the session (pairing and allowlist), permission prompts
(`default: ask`), and, for outward actions in the cloud, the consent proxy (`consent/`: keys held by a separate OS user,
single-use consent for the exact payload).

## The development-channels flag

`mila` starts Claude Code with `--dangerously-load-development-channels plugin:mila-telegram@<marketplace>`.
While channels are a research preview, plain `--channels` accepts only plugins on Anthropic's approved list, and
`mila-telegram` is not on it. The flag applies only to the plugin named after it: it does not bypass permission
prompts or load other channels. Who can write to the session is limited by the plugin's pairing and allowlist
(`/mila-telegram:access`). Once the plugin is accepted into Anthropic's marketplace, the launcher moves to `--channels`.
The flag does not override organization policy: on Claude Team and Enterprise, channels work only after the
organization admin enables them (`channelsEnabled`).

## Ground rules for everyone

- Never commit tokens, API keys or chat exports. `gitleaks` scans the whole history on every push and pull request (`.github/workflows/gitleaks.yml`).
- Archives made by `mila backup` exclude secrets; still treat them as private.
- One Claude subscription login belongs to one person; do not share it.
