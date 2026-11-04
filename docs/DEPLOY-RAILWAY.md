# Mila Agent on Railway

> **Steps 1–5 tried live on 4 November 2026** (a new Railway account, the trial). Prices and plan limits change —
> check them on railway.com. · *Шаги 1–5 проверены вживую 04.11.2026; цены и лимиты тарифов — на railway.com.*

Mila is a digital employee in Telegram: one container with Claude Code, the Mila skills and the Telegram plugin. On Railway
it runs as one service with one volume. You need a Telegram bot and your own Claude account (Pro or Max subscription, or an
Anthropic API key); Railway bills its own usage separately (new accounts get a trial credit).

## 1. Before you start
- **A bot:** Telegram → @BotFather → `/newbot` → keep the token (you paste it on a page in step 4, not in a variable).
- **Railway account:** railway.com → sign up with GitHub. Verify the account (railway.com/verify) — until then outbound network
  is limited and Mila may not reach Telegram or Anthropic.

## 2. Create the service
1. Railway → **New Project** → **Deploy from GitHub repo** → `shakhruz/mila-agent`. Railway builds `./Dockerfile`.
2. Service → **Volumes** → add a volume, mount path **`/home/agent`**. Everything Mila keeps (memory, files, sign-in, keys)
   lives there; without it a redeploy starts from zero.
3. Service → **Settings → Networking → Generate Domain**, port **8080**. This address is only for two one-time pages:
   the bot token now and, later, a voice key if you want one.

No variables are needed. (Optional: `OWNER_ID` — your numeric Telegram id; `TZ` — your time zone, e.g. `Asia/Tashkent`.)

## 3. Deploy
Press **Deploy**. The first build takes a few minutes. In **Deploy Logs** wait for a line with your domain.

## 4. Bot token — one field
Open `https://<your domain>/` → paste the bot token → **Save**. The page checks it with Telegram, shows a button
**Open the bot**, and closes itself. The token is kept on the volume, readable only by the container.

## 5. Your Claude — from Telegram
In the bot press **Start** (that pairs you as the owner), then follow its message: it sends a «Sign in to Claude» link,
you sign in with your own account and send the code back in the chat. Mila confirms and introduces herself.
Using an Anthropic API key instead: Railway → **Variables** → `ANTHROPIC_API_KEY`, then redeploy.

## 6. Voice (optional · not yet tried live on Railway)
Ask Mila «I want to send voice messages». She sends a one-time page for a Deepgram key (free trial credit); for Uzbek —
a Groq key. You paste the key on the page, not in the chat.

## Updating
Railway redeploys when the repository changes (or press **Redeploy**). Your volume stays: new skills reach Mila on the next
start; a CLAUDE.md or constitution you edited is kept, the new version is put beside it as `.new`.

## If something is wrong
| What you see | What to do |
|---|---|
| The bot is silent, logs show network errors | Verify the Railway account (railway.com/verify), then **Redeploy** |
| «Out of memory» and restarts | The trial gives a small memory limit per service; a paid plan has more |
| The token page says the link no longer works | **Redeploy** — the page opens again while there is no token |
| Mila greets you again after a restart | Update to the latest version — the conversation now continues after a restart |
