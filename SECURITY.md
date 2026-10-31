# Security policy

Mila runs an AI agent that can read and write in Telegram chats and on a
machine, so security reports are taken seriously.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's "Report a vulnerability" (private security
advisory) on this repository, or e-mail hello@milagpt.io with "security" in the subject.
Please include what you found, how to reproduce it and the impact.
We acknowledge every report within 5 business days.

## Scope

In scope: the hooks and tools in `install/` and `templates/`, the send-guard, the
installer and bootstrap scripts, secret handling in backups, access control and
pairing flow guidance.

Out of scope: vulnerabilities in Claude Code, Telegram or other upstream software
(report those to their vendors), and misconfiguration of your own server.

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
