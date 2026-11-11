# Modules — what a newborn Mila is made of

*Русский — [MODULES.ru.md](MODULES.ru.md).*

**The map.** Fifteen modules, each in one paragraph: what it gives a person, what it consists of, and an honest mark of its state. The marks are four, and they mean exactly this:

| Mark | Meaning |
|---|---|
| **in the core** | in a released version — an installed Mila has it |
| **accepted, awaits release** | reviewed and merged into the main branch, not in a release yet |
| **in development** | being designed or written; nothing to install |
| **as a pack** | not part of the core — installed on top, by the owner's «yes» |

One module often carries several marks: its base is released while a newer part is still on the way. Each part is marked separately.

## 1. Mind
Mila knows who she is, holds what she took on, and ends every answer with the next move. More on a separate page: [MIND.md](MIND.md).
- **in the core** — the constitution (`CONSTITUTION.md`), the qualities (`canon/QUALITIES.md`, `canon/BAZA-MILY.md`), getting acquainted (`skills/onboarding`), coming with a decision, not a question (`skills/iniciativa`).
- **accepted, awaits release** — the next move (`skills/sleduyushchij-hod`), forks (`skills/razvilki`).

## 2. Passport
A key of her own, a passport, a birth certificate, a recovery envelope the owner keeps.
- **in development** — nothing of it is in the core yet.

## 3. Intellect and voice
Mila thinks with Claude through Claude Code on the owner's own subscription; with a transcription key set she reads voice messages as text.
- **in the core** — the way she speaks (`skills/mila-speech`, `skills/communication`), voice-to-text (`install/transcribe-voice.sh`).

## 4. Telegram
The owner's private chat, the groups he connected, topics, buttons. The bot itself is the plugin `mila-telegram` — a separate repository ([mila-telegram.md](mila-telegram.md)).
- **in the core** — the private chat (`skills/owner-dm`), groups (`skills/mila-in-chat`), topics (`skills/topics`), cards with buttons (`skills/cards`), text for copying (`skills/copyblock`), escalation (`skills/escalate-to-owner`), the send guard (`templates/home/.claude/hooks/send-guard.py`).
- **accepted, awaits release** — reading the owner's personal Telegram account and putting drafts (`skills/shturman`).
- **in development** — widgets (status of a module in one message); sending from the personal account through the Lock.

## 5. Memory and journals
What was done, what went wrong, what is remembered between sessions.
- **in the core** — the session (`skills/mila-session`), the memory audit (`skills/memory-audit`), the journal of deeds (`skills/dela`), the cost of turns (`install/records.py`).
- **accepted, awaits release** — the problem journal (`skills/problemy`).

## 6. Tasks
Take a task, clarify it, bring it to a result with proof.
- **in the core** — `skills/tasks`, `skills/tasks-discipline`, `skills/mila-tasks`, `skills/utochnenie-zadach`, the inbox (`skills/inbox`, `skills/inbox-triage`).

## 7. The Scheduler
Jobs on time, outside the session: [SCHEDULER.md](SCHEDULER.md).
- **in the core** — setting jobs (`skills/raspisanie`), the service (`install/baraban.py`), the loop in the image (`docker/entrypoint.sh`).
- **accepted, awaits release** — the timer on a laptop and the check that the service is running before a time is promised.

## 8. The Safe
Keys and passwords past the chat, personal data as labels, an outside action only after the owner's press: [SAFE.md](SAFE.md), [CONSENT.md](CONSENT.md), [THREAT-MODEL.md](THREAT-MODEL.md).
- **in the core** — one-time links for keys (`skills/safe-link`), the personal-data vault (`skills/pd-vault`), the consent proxy (`consent/consent_proxy.py`).
- **in development** — a wallet; the recovery envelope (with the Passport).

## 9. The Archive
Every message kept; a copy of the home the owner can take away.
- **in the core** — the receiver's archive of messages ([ARCHIVE.md](ARCHIVE.md)), a copy of the home without secrets (`install/backup.py`), export and move (`skills/mila-export`).
- **in development** — an encrypted archive sent to the owner on a schedule (with the Passport).

## 10. The Library
Packs: a role and skills on top of the core, installed by a button. A pack's code is never run on install.
- **in the core** — the catalog and its trust chain (`skills/library`), installing and removing packs (`skills/packs`), the packs that come with the core (`packs/`).
- **in development** — a pack's status widget; a catalog of Milas next to the packs.

## 11. Quality
She checks herself before she says «done».
- **in the core** — `skills/self-check`, `skills/verify`, `skills/oglyadka`, `skills/obratnaya-svyaz`, `skills/plain-words`, `skills/import-review`.

## 12. Subscription
How much of the owner's Claude plan is left, and a watch on the limit.
- **in the core** — `skills/subscription`, `skills/subscription-limits`, `install/limit_watch.py`.

## 13. Health
Why the bot is silent, what version she is, how to update and roll back.
- **in the core** — the doctor (`install/doctor.py`), updates by the owner's «yes» (`skills/mila-update`).

## 14. Birth and rebirth
From nothing to a working Mila: a laptop, a server, a container, a cloud ([CLOUD.md](CLOUD.md)).
- **in the core** — `install/get.sh`, `install/install.sh`, `install/onboard.py`, the image (`docker/Dockerfile`, `docker-compose.yml`, `railway.json`).
- **in development** — rebirth: the same Mila on a new machine from the envelope and the owner's twelve words.

## 15. The Game
A calm game inside the chat — a garden and a puzzle.
- **in development** — nothing of it is in the core.

## Outside the fifteen
- **as a pack** — images and video (`packs/kartinki`), a screen at home (`packs/dom`), roles for a business (`packs/manager`, `packs/business-assistant`, `packs/clinic`, `packs/travel-agency` and others in `packs/`).
- **in development, as a pack** — «Contractors»: a register of the people who do work for the owner.

## In the code
| What | Where | Test |
|---|---|---|
| Every skill has a name and a description | `skills/`, `packs/` | `tools/check_frontmatter.py` |
| All tests in one command | `tests/run_all.sh` | — |
| This page names only paths that exist | `docs/MODULES.md` | `tests/test_docs_pairs.py` |
| What Mila can and cannot do, claim by claim | `docs/WHAT-MILA-CAN.md` | — |
