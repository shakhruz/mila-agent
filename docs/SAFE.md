# Mila Safe — keys and passwords past the chat

*Русский — [SAFE.ru.md](SAFE.ru.md).*

**What it is.** When a task needs a password, an API key, a site login or a bank card, Mila never asks for it in the chat or by email. She asks for a one-time link instead. The person opens it, types the values on a page, and they land straight in a locked file in Mila's home. They don't pass through the chat or her memory, and the person who issues the link never sees them either.

## How a link is issued
- `tools/seif/vault-link.sh <home> <FIELD>[,<FIELD>…] [--name <file>] [--to <telegram id>] [--ttl 30] [--lang ru|en|uz|zh]`
- Fields are written in capitals: `OPENROUTER_API_KEY`, `SITE_LOGIN`, `SITE_PASSWORD`, `CARD_NUMBER`, `CARD_EXPIRY`.
- One link, one use, lives 30 minutes. Opening it (or a Telegram preview opening it) does not use it up; only **Save** does.
- The page language comes from the owner's language, can be set with `--lang`, and can be switched on the page.

## Where the key goes
- `work/secrets/<file>.env` in Mila's home: folder 700, file 600, owned by the home's owner. Values already in the file are kept.
- The journal (`journal.jsonl` of the safe service) records who, when, which home, which file and which fields — **never values**.
- Mila gets a note in her inbox: «these fields appeared in the safe».

## How Mila reads it
- Only at the moment of the action, with her own tool: `python3 skills/safe-link/scripts/safe_read.py <file> --check FIELD` tells whether a field is there, without the value. In code, `read_safe("<file>")["FIELD"]` gives the value straight to the service call.
- In the chat — only a mask: `****1234`.
- A file with permissions wider than 600 is refused: someone has opened the safe.

## When the job is done
- `seif.py forget <home> <file> <FIELD>[,<FIELD>…]` removes the fields. The journal records what was erased and when, without values.

## What is not allowed
- Asking for a secret in the chat or by email. If someone sent one anyway, Mila does not repeat it and asks them to change it.
- Printing, logging or forwarding values; putting them into memory, notes or a report.
- Keeping a card or passport longer than the job needs.

## Running the safe service
- `seif.py serve --port 7693` listens on 127.0.0.1 only. Put it behind your web server for `/v/<token>/` (`tools/seif/Caddyfile.snippet`, `tools/seif/seif.service`). Copy `seif.py`, `mila_i18n.py`, `mila_style.py`, `mila-portrait.jpg` and `locales/` together into the service folder: the page takes its look from `mila_style.py` (without the portrait file it simply has no portrait).
- Settings come only from the environment: `SEIF_BASE` (link address), `SEIF_HOMES` (folder of Mila homes), `SEIF_DIR`, `SEIF_UID`.

## Own safe — a Mila on your own computer
`seif.py own <FIELD>[,<FIELD>…] --name <file>` — no service and no administrator: Mila opens the safe page on 127.0.0.1 for one link, closes it as soon as you press Save (or after 10 minutes), and the key lands in `~/work/secrets/<file>.env`. The link opens **only on the same computer** — nothing is exposed to the network.

## Known limit
A Mila in a container or on a server without the safe page cannot take a key through a page yet, and she says so plainly. **What to do now:** don't send the key in the chat. In a container put it in an environment variable at start — `docker run -e OPENROUTER_API_KEY=…` or the variables field in your host's panel. On a laptop use the own safe above, or a file `~/work/secrets/openrouter.env` with the line `OPENROUTER_API_KEY=…` (no quotes, no spaces) and permissions 600 (`chmod 600`); the same for `GROQ_API_KEY` in `groq.env`. Mila sees such a key at once (the variable wins over the file) and never shows the value.
