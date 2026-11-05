# What Mila can do — and what she cannot

Mila Agent is Claude Code with the Telegram plugin ([mila-telegram](mila-telegram.md)), hooks and core skills. Everything below is
what the code in this repository does. The «How we know» column says what checks it:
- **Claude Code** — a tool of Claude Code itself, not ours;
- **test** — a test in this repository (named);
- **not checked** — no test and no live run.

Nothing here has been run live on a clean install of this release yet.

## In the core (no extra keys)

| What she does | Where | How we know |
|---|---|---|
| Talks to you in Telegram DMs: text, buttons, files to you up to 50 MB, edits, reactions | plugin `server.ts` | test: plugin `bun test` |
| Works in groups you connect, in the mode you choose on a card: lead the chat, on mention, observer, only me, refuse | plugin `group-mode.mjs` | test: plugin `group-mode.test.ts` |
| Sees photos as they arrive; other files on request, up to 20 MB (Telegram's limit for bots) | plugin `server.ts` | test: plugin `bun test` |
| Searches the web and reads web pages | Claude Code `WebSearch`, `WebFetch` | Claude Code |
| Reads images, PDFs and documents; writes and edits files; runs commands in her home | Claude Code `Read`, `Write`, `Edit`, `Bash` | Claude Code |
| Keeps promises as tasks, closes them only with proof | `skills/mila-tasks/task.py`, hooks `task-open.py`, `task-sent.py` | test: `skills/mila-tasks/test_task_clean_home.sh` |
| Asks you for a decision with a card and buttons | `skills/cards/cards.py` | test: `skills/cards/test_cards.py` |
| Runs jobs on a schedule that survive a session restart | `skills/raspisanie` (`mila_cron.py`), `install/baraban.py` | test: `skills/raspisanie/test_mila_cron.py`, `install/test_baraban.py` |
| Stops a reply to a chat you have not connected, and secrets in a reply | hooks `send-guard.py`, `secret-guard.py` | test: `templates/home/.claude/hooks/test_send_guard.py`, `test_secret_guard.py` |
| Replaces phone numbers, cards and passports with labels in what she writes down | hook `pd-mask.py`, `skills/pd-vault` | test: `install/test_pd_mask.sh`, `skills/pd-vault/test_pd_vault.py` |
| When your Claude plan hits its limit, notices it and says when it resets, instead of falling silent | `install/limit_watch.py`, `skills/subscription` | test: `install/test_limit_probe.py` |
| Copies herself to an archive without secrets and restores from it | `skills/mila-export` | test: `skills/mila-export/test_export.sh` |
| Updates herself and installs packs only after your press on a card | `skills/mila-update/update.py` | test: `skills/mila-update/test_packs.py` |
| Brings over an OpenClaw or Hermes agent's memory and skills | `tools/import_agent.py`, `skills/import-review` | test: `tools/test_import_agent.py` |
| Speaks English, Russian and Uzbek on her buttons and service texts | `install/locales`, plugin `i18n.mjs` | test: plugin `i18n.test.ts`, `install/test_doctor_i18n.py` |
| In the container, keeps the Claude, bot and voice keys with a key keeper she uses but cannot read | `docker/mila_keyd.py` | test: `docker/test_mila_keyd.py`; image build `docker/wall_probe.sh` |

## With your own key

| What | Needs | Where | How we know |
|---|---|---|---|
| Voice messages to text | a Deepgram or Groq key (Uzbek — Groq) | `install/transcribe-voice.sh` | test: `install/test_voice_providers.sh` |

## What she cannot do today

| What | Why |
|---|---|
| Answer strangers who write to your bot in a DM | They get a pairing code or no answer, by your access settings. A separate lane for strangers is the next step of the plugin, not in this release. |
| Answer strangers in a group with limited rights | In «lead the chat» mode she answers everyone from the main session, with all her tools. A safe mode for strangers is in work. |
| Read Telegram chat history or search it | The Bot API gives only new messages. |
| Download files over 20 MB | The Bot API limit. |
| Generate images, video or voice | Not in the core. The packs that do it call `genimage.py` and `el.py`, which are not in this repository. |
| Work in WhatsApp, Instagram, email or by phone | Only Telegram in the core. Email — the Mail pack. |
| Pay, send money or sign for you | Not built. |

## Packs — installed by your press

A pack is a set of skills: instructions Mila follows. A pack adds no tools of its own unless the table says so.

| Pack | What it adds | What it needs, honestly |
|---|---|---|
| `manager` — your first manager | customer chats, lead questions, polite refusals, closing a dialog, drafts checked before sending | `crm-dialogs`, `dialog-close`, `polite-no`, `reply-from-examples` call `dialogs_*` tools that are not in this repository; `bot-send` writes a request for a sender that is not in this repository. Customers in the bot's DM — see «cannot» above. |
| `business-assistant` | day board, readiness before events, plan-vs-fact of the week, DM review | not checked |
| `content-expert` | posts in your voice, flashcards, infographics, mini-podcasts, explainer videos, YouTube research | pictures and voice need `genimage.py`, `el.py` and OpenRouter / ElevenLabs keys — the scripts are not in this repository |
| `kartinki` — images and paid generations | picks a model with a price, keeps a ledger of spending | your OpenRouter key; `spend` refers to `media_ledger.py`, not in this repository; the ledger itself — test: `packs/kartinki/spend/test_spend_tap.py` |
| `reklama` — ads | A/B test card, ad check, one tag per ad | not checked |
| `pochta` — mail | rules for outbound email: address check, «sent» only on the tool's answer | a mail tool of yours (Gmail, SMTP…) — the pack brings none |
| `uzbek` | living Uzbek in outward texts | Uzbek voice — a Groq key |
| `dom` — home | Yandex Alice speaker, a TV or monitor as her screen, your tastes | a screen key from our service |
| `owner-telegram` | reads your personal Telegram, drafts in your voice | a user session of your account — read its warning first |
| `jev` | decides fast whether a group message is for her | test: `packs/jev/jev/test_jev.py` |
| `clinic`, `travel-agency`, `webmaster` | bookings for a clinic; a travel agency's role; client sites | `webmaster` refers to build scripts not in this repository |
