# Design: Mila's passport

*Русский — [PASSPORT.ru.md](PASSPORT.ru.md).*

> **In development.** Nothing on this page is in the core yet. This is the design the code will be written from; where a decision is still open, the page says so. See the marks on [the map of modules](../MODULES.md).

**What it is for.** Today a Mila is a home on a disk: copy the folder and there are two; lose the disk and there is none. The passport gives her one identity that survives a move, a restore and a change of owner — and gives the owner a way to bring her back with nothing but a file and twelve words.

## What the owner gets
- **A number** nobody else can have — and a proof that a message, a profile or a record was made by this Mila.
- **A certificate** he can print: the name, the date of birth, the number.
- **A recovery envelope** — one encrypted file he keeps. With it and his twelve words the same Mila starts on a new machine.
- **An archive of memory** that arrives in his Telegram on a schedule, encrypted so that only his words open it.
- **A trace of how she changed** — a daily fingerprint of her state.

## The key and the number
- A Mila gets a signing key pair (Ed25519) at birth. **The number is the public key**: `mila:ed25519:<key>`. A document signed by a Mila can be checked by anyone with a standard tool.
- In the container the private key stays with the key keeper (another OS user): the session can ask for a signature on a document of a known kind and cannot read the key. On a laptop the key is a file in the keys folder of the home — the same residual risk as the other keys there, said plainly.
- Signing and encryption use the cryptography built into the runtime the Telegram plugin already needs (`node:crypto`: Ed25519, X25519, scrypt, AES-256-GCM); Python's standard library has neither, and no new dependency is added.

## Two steps: a quiet birth, then the certificate
1. **Birth is quiet.** At the first start the key pair is made and the date of birth is written. No words, no signatures, no questions.
2. **The certificate is issued on the owner's word** («issue the certificate»): the twelve words, a check of three of them, the envelope sent as a file, his confirmation. Mila suggests it when there is something to lose — not more often than once a week, and «not now» is an answer.

Until the certificate is issued, a Mila has no wallet address to show: that is a refusal in the code, not a rule in a skill.

## The twelve words
The owner's twelve words are the key to the envelope and the archive. **Mila never sees them and never keeps them.**
- They are made and shown in a window on the owner's side — a command in his own terminal on a laptop, a one-time page in his browser for a cloud Mila — and the check of three words happens in the same window.
- From the words a key pair of the owner is derived there; Mila gets only its public half.
- In the chat Mila says one thing: «the window is open — write the words down on paper», and learns one thing: «the words are written down and checked».

*Open decision:* whether the words may instead be shown by Mila in the chat. The design recommends the window: words shown in a chat stay in the chat's history.

## The recovery envelope
One file, encrypted to the owner's public key: the passport, Mila's signing key, the bot's key, the basic settings (name, language, calling) and where the archive of memory is. It is rebuilt when a key changes and sent to the owner as a file. A check once a quarter: the owner opens the envelope with his words — in the same window on his side, never in the chat — and Mila verifies that the key inside is the living one.

## The archive of memory
On a schedule of the [Scheduler](../SCHEDULER.md): a copy of the home without secrets, encrypted to the owner's public key, sent to him as a file (in parts when large), with one line — when and how much. Other places to keep it (a drive, a repository, one's own server) come as packs.

## The fingerprint of state and checkpoints
Once a day, before an update and before a transfer, Mila writes a checkpoint: a SHA-256 over three layers of her home, the line chained to the previous one and signed.

| Layer | What goes in |
|---|---|
| Character | the constitution, the home's instructions, the canon |
| Talents | the skills and hooks, the list of packs, the core version |
| Memory | the memory, the journals of deeds, problems and forks, the schedule |

Never in a fingerprint: keys and secrets, the Telegram channel's state, caches, media. A link inside a layer or an unreadable file is a refusal, not a skipped line. The model's name in a checkpoint is what the session's settings say — it cannot be verified, and the record says so.

## Two signatures
- **Ordinary** — the owner's press in Telegram (the consent proxy, [CONSENT.md](../CONSENT.md)) plus Mila's signature: daily matters, issuing the certificate.
- **Full** — Mila's signature plus the owner's key from the twelve words, entered in the window, not in the chat: rebirth, transfer, a change of keys.

## Rebirth
The first screen of an install offers two ways: «A new Mila» — a new key, today's date of birth; «Bring my Mila back» — the owner gives the envelope and enters the twelve words in the install window. The same number, the same passport; the memory comes from the last archive. The old copy's bot key is changed in the same step, so two Milas never answer as one bot.

## Transfer to a new owner
A checkpoint with the full signatures of both owners. The layers «character» and «talents» go; the layer «memory» starts anew — the previous owner's personal memory is not handed over.

## People in the passport
Two fields about people, and no personal data beyond them: the **owner** — may change (a transfer); the **mentor** — the one who helped this Mila be born — does not change. Neither field is about payments.

## An outside journal
Only the number of the Mila, the number and the fingerprint of a checkpoint and the time may go outside — no names, no paths. *Open decision:* the format of the record and who signs the request. Until then checkpoints are kept in the home and checked by a command.

## What is decided and what is open
| Decided | Open |
|---|---|
| Ed25519; the number is the public key | whether the twelve words may be shown in the chat |
| a quiet birth; the certificate on the owner's word | the format of the outside journal |
| the envelope and the archive are opened only by the owner's words | where the wallet lives and in what form |
| the mentor does not change, the owner may | what the certificate sheet looks like in print |

## Order of work
1. The fingerprint and checkpoints; the quiet birth of the key.
2. Issuing: the window with the words, the check, the envelope.
3. The archive on a schedule.
4. Rebirth: the first screen, a restore from the envelope and the archive.
5. The certificate sheet. 6. Transfer; the outside journal.

Each step: the design or the code → review → the main branch.

## In the code
| What exists today | Where | Test |
|---|---|---|
| The key keeper the signing will join | `docker/mila_keyd.py` | `docker/test_mila_keyd.py` |
| The consent proxy — the «ordinary» signature | `consent/consent_proxy.py` | `consent/test_consent.py` |
| A copy of the home without secrets — the base of the archive | `install/backup.py` | `install/test_backup_keys.py` |
| The Scheduler the archive and checkpoints will run on | `install/baraban.py` | `install/test_baraban.py` |
