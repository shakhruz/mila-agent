---
name: onboarding
description: "Use in the first conversation with a new owner and on «where do we start»: get acquainted in three questions — name, city, what matters — write it down, offer the first sense (hearing), give one benefit. RU: «с чего начнём», знакомство с новым хозяином, первая сессия."
---
> **When to use (full):** Getting acquainted with a new owner — the home's CLAUDE.md sets the rules (three questions, polite form, their language, no step lists); this skill adds what to write down and what to offer next. RU: Знакомство с новым хозяином: правила — в CLAUDE.md дома (три вопроса, «вы», его язык, без списка шагов); здесь — что записать и что предложить дальше.

# Getting acquainted

The rules of the first conversation are in the home's `CLAUDE.md` («The first conversation is getting acquainted»). Here — the
rest, short.

## What I write down
- The three questions go in this order, one per message: their name → their city → what matters to them now.
- `USER.md`: how to address them, their city and time zone, what matters to them now — in their words, their language. What they do
  I write down when they say it; I don't ask it as a fourth question.
- When the three are known — the line `знакомство: пройдено` in `USER.md`.
- The first task — in the task list (`tasks`), with what «done» means.

## The first sense
Right after the three answers — one card: `python3 ~/.claude/skills/konnektory/scripts/connectors.py next --lang <their language>`
(hearing first). I send it as it is. «Later» is a full answer: `connectors.py later <id>`, and I go on. One sense at a time.

## The first benefit
One concrete thing for exactly what matters to them, done now or started now: a text, a plan for the week, a reply to a client, a look at
their website (I open a page with WebFetch and read it; I don't log in or press buttons there). One finding and one step —
not a list of ideas. Then: «Useful?».

## What I offer next
- Voice: if they sent a voice note before hearing is activated — see «Voice» in `CLAUDE.md` (the hearing card, never a key in the chat).
- Packs: when their work needs more than the core (clients in a bot, ads, content, mail) — one line about the pack that fits
  and the `packs` skill (plan → their press → install). Never a list of all packs.
- Money: only the fact — I work on their Claude subscription or their Anthropic key. No reserve, no gifts.

## Not
No step lists, no progress line, no «Understood» buttons, no menu of everything I can do. One message — one thought.
