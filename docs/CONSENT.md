# Consent: an outside action only after the owner's press

In Mila Agent, an action that leaves the machine on the owner's behalf — a post, a paid generation, a message sent as the owner —
can be run by a separate process, the consent proxy (`consent/consent_proxy.py`), as the receiver's OS user `mila-io`. The
session cannot run it itself: the service keys are with the proxy, not with the session. The session only asks.

## How a request goes

1. The session asks over `/run/mila-io/consent.sock` (`consent/consent_client.py`): a kind (category) and the payload.
2. The proxy draws the card itself in the owner's private chat: the whole text (a long one in parts before the card),
   where it goes, the attachments. A field the card does not show is refused.
   A text or a target with invisible or direction-changing characters, or not in its NFC form, is refused: the owner sees
   exactly what will run.
3. Only the owner's press in the private chat counts: a signed button, checked by the proxy. The receiver passes the press to
   the proxy over `/run/mila-io/consent.io.sock`, which only `mila-io` reaches, and says the outcome on the button.
4. The «yes» is for exactly that action (a hash of the kind, the payload and every attachment's content), once, for 15
   minutes. A changed text or file asks again.
5. A «no» holds for a day: the same action is refused without a new card. Three «no» in a row for a kind: no more cards of that
   kind until a «yes» or a day. A card nobody answered in 15 minutes is «expired» — silence is not consent.

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
| permissions: terms, ceilings, receipts, Stop | `mandate_ask()`, `mandate_fits()`, `receipt()`, `mandate_stop()` |
| the chain and its check | `consent/decisions.py` |
| the press goes to the proxy | plugin `consentPress()` (`receiver.ts`), `TELEGRAM_CONSENT_IO` |
| in the image, categories from the image, sockets | `docker/entrypoint.sh` (root step, supervisor); `consent/categories.json` |
| checked | `consent/test_consent.py`, `test_decisions.py`, `test_mandates.py`; plugin `consent-io.test.ts`; `docker/test_docker_files.sh`; in the image build `docker/wall_probe.sh` |

## Not verified live yet

- A real card in the owner's chat, the press, the action, the receipt — on a stand with a real bot.

## What stays open

- Kinds still asked their own way, not through the proxy yet: pack installs and updates (`update.py`), sending from the
  owner's bot (`bot-send`), paid generations (`spend.py`). They move to one `request` next.
- The notification gate (urgent / card / summary, quiet hours, a limit on cards at night) and the anchor in the evening summary.
- The cards are in Russian only; in the owner's language — with the gate.
