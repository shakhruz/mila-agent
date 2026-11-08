# Mila in the cloud — two ways, one page

Mila Agent is one container: Claude Code, Mila's skills and the Telegram plugin. Pick where it lives. Either way you need
a Telegram bot (@BotFather → `/newbot`) and your own Claude (a Pro/Max subscription or an Anthropic API key). Keys and
accounts are yours: you make them, Mila never sees your Claude sign-in token.

| | **Railway** | **Hostinger VPS** |
|---|---|---|
| Start | [**Deploy on Railway**](DEPLOY-RAILWAY.md) — steps 1–5 (a one-click template link comes here once it is published) | [**Deploy on Hostinger**](https://www.hostinger.com/docker-hosting?compose_url=https://raw.githubusercontent.com/shakhruz/mila-agent/main/docker-compose.yml) |
| What you do | sign up (trial credit), press Deploy, open the page it gives, paste the bot token | choose a VPS plan, paste the bot token in the Docker panel, Deploy |
| Then | press Start in your bot → «Sign in to Claude» → send the code back | the log shows a pairing code → `/pair CODE` to your bot → «Sign in to Claude» |
| Tried live | yes, 04.11.2026 (voice — not yet) | not yet |
| Details | [DEPLOY-RAILWAY.md](DEPLOY-RAILWAY.md) | [DEPLOY-HOSTINGER.md](DEPLOY-HOSTINGER.md) |

Hostinger pulls the public image of the latest release, `ghcr.io/shakhruz/mila-agent:latest`; Railway builds the same image from
this repository. Both keep everything Mila has on one volume (`/home/agent`), so an update or a restart keeps her memory.

After the start: write «hi» to your bot. Voice messages — ask Mila «I want to send voice»; she sends a one-time page for a voice key.

---
**RU · Мила в облаке — два пути.** Railway: кнопка «Deploy on Railway» → страница → токен бота → Start в боте → вход в Claude
из чата. Hostinger: кнопка «Deploy on Hostinger» → тариф VPS → токен бота в панели Docker → код пары из журнала → `/pair` → вход
в Claude. Ключи и аккаунты — ваши; Мила свой вход в Claude не видит.
