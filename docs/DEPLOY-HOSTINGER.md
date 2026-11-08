# Mila Agent on a Hostinger VPS — in 5 minutes

> **Not yet tried live on Hostinger** — the container itself is tested; report issues. · *Ещё не пробовали вживую на Hostinger — сам контейнер проверен; о проблемах — сообщите.*

[![Deploy on Hostinger](https://assets.hostinger.com/vps/deploy.svg)](https://www.hostinger.com/docker-hosting?compose_url=https://raw.githubusercontent.com/shakhruz/mila-agent/main/docker-compose.yml)

Mila is a digital employee in Telegram: one container with Claude Code, the Mila skills and the Telegram plugin.
It talks to Telegram outward only — no open ports.

## What you need (1 value)

| Variable | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → `/newbot` → copy the token |
| `CLAUDE_CODE_OAUTH_TOKEN` *(optional)* | Leave it empty: after the start write /start to your bot — it sends a «Sign in to Claude» button, you sign in with your own account on the phone and send the code back in the chat. Or paste a token from `claude setup-token` here |
| or `ANTHROPIC_API_KEY` | Pay-as-you-go instead of a subscription: console.anthropic.com → API keys |
| `OWNER_ID` *(optional)* | Your numeric Telegram id (e.g. from @userinfobot). Empty → a pairing code in the log instead |

## Steps

1. Click **Deploy on Hostinger**, choose a VPS plan, finish checkout.
2. Docker Manager opens with Mila's compose file. Add the variables above in the environment field.
3. Deploy. The server pulls the ready image of the latest release (a minute or two) — nothing is built there.
4. Open the container **log**: it shows `pairing code ABC123`. Send `/pair ABC123` to your bot in Telegram — you are the owner
   (with `OWNER_ID` set, or a birth code, this step is skipped). The bot sends a «Sign in to Claude» button: sign in with the
   account that has your Claude subscription, copy the code Anthropic shows and send it to the bot within 10 minutes. The bot
   deletes that message, says «connected» and starts. Anyone who only knows the bot's name gets one line and nothing else.
   The sign-in is a long-lived token (about a year) kept in the `mila-home` volume; to cut it off, revoke it in your Claude
   account settings or delete `.mila-auth/oauth_token` in the volume and restart.
5. Write «hi» to your bot.

With `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` set, step 4 is skipped; then, without `OWNER_ID`, the log shows a
6-character pairing code to send to the bot.

## Good to know

- Your memory, skills and the bot's state live in the `mila-home` volume — they survive restarts and updates.
- Changed a variable? Restart the container; the token is re-read on every start.
- Health: the container is healthy when the Telegram receiver and the Claude session both run.
- Nothing secret is stored in the image or in this repository.
- **What the container does not ask.** Inside the container Mila runs commands without the permission cards a laptop
  install shows: the boundary is the container itself. The bot token and your Claude token are in the session's environment —
  the session can read them. Give the container nothing else you would not give Mila. See the
  [threat model](THREAT-MODEL.md#the-one-container-setup).
- The Telegram plugin loads as a Claude Code development channel (research preview), the same as `mila` on a computer.
- Building it yourself with **podman** instead of Docker: `podman build --format docker -f docker/Dockerfile .` — the OCI format drops the HEALTHCHECK.
