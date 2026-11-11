# Consent: an outside action only after the owner's press

In Mila Agent, an action that leaves the machine on the owner's behalf — a post, a paid generation, a message sent as the owner —
can be run by a separate process, the consent proxy (`consent/consent_proxy.py`), as the receiver's OS user `mila-io`. The
session cannot run it itself: the service keys are with the proxy, not with the session. The session only asks.

## Four words

- **Lock** (RU: Замок) — an action that does not go further without the owner's key: a word in his name, money, anything that cannot be undone. A lock is a mechanism, not a promise: the consent proxy runs such actions, the session only asks. Where there is no proxy (a laptop), there is no lock — Mila says so and prepares a draft for the owner to act on himself.
- **Consent** (RU: Согласование) — the owner opens a lock with a button, for this text and this time. A changed character or target — a new card. One press, one action; every step is in the consent journal. Silence is not consent.
- **Choice** (RU: Выбор) — when the decision is the owner's, Mila comes with options A/B/C, what each leads to, her recommendation and its ground (`skills/cards`, `skills/iniciativa`).
- **Fork** (RU: Развилка) — on her own reversible work Mila goes ahead by the recommended option, says «while you are silent I do B on my side, nothing goes out», and logs the point: what she chose, why, what to redo on a switch (`skills/razvilki`). The owner picks another option later — she returns to the point. No fork behind a lock.

The same in Russian for Mila herself: `canon/ZAMOK.md`.

## How a request goes

1. The session asks over `/run/mila-io/consent.sock` (`consent/consent_client.py`): a kind (category) and the payload.
2. The proxy draws the card itself in the owner's private chat: the whole text (a long one in parts before the card),
   where it goes, the attachments. A field the card does not show is refused.
   A text or a target with characters that do not show (by their Unicode property: format, control, separators, private
   use, unassigned, «empty letters»; a joiner inside an emoji passes) or not in NFC form is refused: the owner sees
   exactly what will run.
3. Only the owner's press in the private chat counts: a signed button, checked by the proxy. The receiver passes the press to
   the proxy over `/run/mila-io/consent.io.sock`, which only `mila-io` reaches, and says the outcome on the button.
4. The «yes» is for exactly that action (a hash of the kind, the payload and every attachment's content), once, for 15
   minutes. A changed text or file asks again.
5. A «no» holds for a day: the same action is refused without a new card. Three «no» in a row for a kind: no more cards of that
   kind until a «yes» or a day. A card nobody answered in 15 minutes is «expired» — silence is not consent.

## Night and flood

- In the owner's quiet hours (22:00–08:00 in the time zone `MILA_TZ` or `TZ`; no time zone — no quiet hours) a card waits for
  the morning: the session gets «deferred», the card goes out after 08:00 and its 15 minutes count from then. A file changed
  overnight — the card expires instead of showing something else.
- More than 10 cards an hour — refused: the owner is not flooded.

## Kinds in the image

`consent/categories.json` (from the image, never from the session's files):
- `send_as_owner` — a message from the owner's bot to named chats (numeric ids); the `bot-send` skill uses it in Mila Agent.
- `spend` — a paid generation: the card shows what, where and the forecast; standing permissions allowed (per service).
- `pack`, `update` — consent only: the proxy records «confirmed» with the exact action's hash, `update.py` runs the install
  or the update itself after `confirmed()` finds it (the chain intact, after it asked, not used before). A `--yes` string from
  the session is not an owner's «yes».
- `publish_zernio` — off until the owner turns it on.

## The notification gate

Other scripts tell the owner through the proxy (`{"op": "notify", "level", "kind", "text"}` on the session socket):
- urgent — at once, even at night, but only `login_lost` and `security` (the owner's rule), at most 5 a day;
- anything else waits for the summary at 09:00 and 19:00 in the owner's time zone — one message;
- the same thing once a day; invisible characters are removed.

## Standing permissions

The session may ask for a permission; the proxy draws the card with the exact terms; only the owner's press opens it.
- At most 7 days and $10 a day (the config can only lower it), named targets only, a number of actions a day.
- Inside it an action runs without a card, and the owner gets a receipt with today's count and money and a **Stop** button.
  Outside it — over the day's money or count, another target, after the term, after Stop — the usual card.
- Only kinds marked `mandate_ok` can have one.

## The decisions journal

`~/.claude/channels/telegram/io/consent/decisions.jsonl` (0640: the session reads, cannot write): every step — asked,
granted, declined, used, executed, expired, denied, mandate_open / mandate_use / mandate_stop, category on/off. No text of the
action, only its hash and short fields. A hash chain: a changed, inserted or removed line breaks it; a cut tail shows against
an anchor `n:h12` kept outside the machine. `python3 consent/decisions.py verify FILE [--anchor N:H12]`, `… head FILE`.

## In the image

- Started by the receiver's supervisor once there is an owner (`io/owners.json`); with `owners.pending` it waits.
- Its categories come from the image (`consent/categories.json`), never from the session's files: a category runs a command as
  `mila-io`. In this version: `publish_zernio`, off until the owner turns it on.
- The bot goes through the key keeper; the session's environment has `MILA_CONSENT_SOCKET`.

## Claimed ↔ in the code

| Claim | Where |
|---|---|
| the card drawn by the proxy, the exact action's hash, once, 15 min; no invisible characters | `consent/consent_proxy.py` `request()`, `hidden()`, `digest()`, `preview()`, `callback()` |
| a «no» a day, three in a row, silence = expired | `request()` (`DECLINE_MEMORY`, the streak), `sweep()` |
| night: cards wait for the morning; at most 10 an hour; the owner's language | `quiet()`, `flush()`, `MAX_CARDS_HOUR`, `lang()`, `W` |
| consent-only kinds, the tools' check | `execute()` (no `exec`), `action_hash()`, `confirmed()`; `skills/mila-update/update.py` `proxy_consent()`, `cmd_apply()`; `packs/kartinki/spend/spend.py` `proxy_approve()` |
| send as the owner | `consent/executors/tg_send.py`; `packs/manager/bot-send/request_send.py` `via_proxy()` |
| the notification gate | `notify()`, `summary()`, `URGENT_KINDS` |
| permissions: terms, ceilings, receipts, Stop | `mandate_ask()`, `mandate_fits()`, `receipt()`, `mandate_stop()` |
| the chain and its check | `consent/decisions.py` |
| the press goes to the proxy | plugin `consentPress()` (`receiver.ts`), `TELEGRAM_CONSENT_IO` |
| in the image, categories from the image, sockets | `docker/entrypoint.sh` (root step, supervisor); `consent/categories.json` |
| checked | `consent/test_consent.py`, `test_decisions.py`, `test_mandates.py`, `test_night.py`, `test_confirm.py`, `test_tg_send.py`, `test_notify.py`; `skills/mila-update/test_pack_proxy.py`, `packs/kartinki/spend/test_spend_proxy.py`, `packs/manager/bot-send/test_request_proxy.py`; plugin `consent-io.test.ts`; `docker/test_docker_files.sh`; in the image build `docker/wall_probe.sh` |

## Not verified live yet

- A real card in the owner's chat, the press, the action, the receipt — on a stand with a real bot.

## What stays open

- On a plain install (no proxy) packs, updates, `bot-send` and `spend.py` keep their own way of asking.
- Which scripts send through the gate: the gate is there; moving each script (limit watch, feeder alerts) to it — next.
- The chain's anchor in the evening summary.
