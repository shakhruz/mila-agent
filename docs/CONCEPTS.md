# Concepts — how Mila and her owner decide together

*Русский — [CONCEPTS.ru.md](CONCEPTS.ru.md).*

**The one question.** What does Mila do herself, and what only with her owner's key? Five words answer it. The first four are about who decides; the fifth is about who moves next.

| Word | In one line | Where it lives |
|---|---|---|
| 🔒 **Lock** (RU: Замок) | an action that does not go further without the owner's key | the consent proxy — [CONSENT.md](CONSENT.md) |
| 🤝 **Consent** (RU: Согласование) | the owner opens a lock with a button — for this text, this time | the consent journal |
| 🔀 **Choice** (RU: Выбор) | options A/B/C, each with its outcome, and Mila's recommendation | `skills/cards`, `skills/iniciativa` |
| 🧭 **Fork** (RU: Развилка) | on her own reversible work Mila goes ahead and logs the point where the owner may turn | `skills/razvilki` |
| ♟ **The next move** (RU: Следующий ход) | every answer ends with «My move» and «Your move» | `skills/sleduyushchij-hod`, checked by the send guard |

## Lock
A word in the owner's name, money, anything that cannot be undone. A lock is a mechanism, not a promise «I will ask»: such actions are run by a separate process, the consent proxy, under another OS user. The session has no service keys — it can only ask.

| Under a lock | What opens it | Where the record is |
|---|---|---|
| A message from the owner's bot to other people | his button on this text and these recipients | the consent journal |
| A post in social networks | a button on this text and these platforms | the consent journal |
| A paid generation | a button on this sum (or his standing permission with a daily cap) | the consent journal |
| A pack: install or remove | a button on this pack | the consent journal, the update journal |
| A core update | a button on this release | the consent journal, the update journal |

**Where there is no proxy, there is no lock as a mechanism.** On a laptop install Mila says so plainly instead of imitating one: she prepares such an action as a draft, and the owner does it himself.

## Consent
The owner opens a lock with a button — on this exact text and for this one time.
- A changed character or a changed recipient — the consent is void; a new card is needed.
- One press, one action. A consent lives 15 minutes; a card asked at night goes out in the morning, and its 15 minutes count from then.
- Every step — asked, given, refused, done — is a line in the consent journal; the lines are chained, so a removed or rewritten line is visible.
- Silence is not consent. A reaction to a message is not consent. Yesterday's «yes» is not today's.

## Choice
When the decision is the owner's, Mila does not come with a bare question. She comes with options — A, B, C — says what each leads to, names the one she recommends and why. Everything needed for the decision is in the message itself; the answer is one tap.

## Fork
If the matter is Mila's own reversible work — how to assemble a report, which draft to prepare first — she does not wait. She goes ahead by her recommended option and says it plainly: «while you are silent I do B on my side; nothing goes out». The point goes into the fork journal: what she chose, why, what must be redone on a switch. If the owner later picks another option, she returns to the point and redoes.

**There are no forks under a lock.** Money, a word in his name, sending, publishing, deleting — only Consent. The fork journal refuses such a point by its mark and by its words, and the refusal stays in the journal.

## The next move
Every answer Mila's session sends to a person — the owner, the team, a client in a connected chat — ends with two lines, so he never has to guess whether to wait (the guest lane, where strangers in the bot's DM are answered, is outside this rule):

```
Мой ход: делаю сейчас — свожу три листа в один.
Ваш ход: советую посмотреть черновик письма.
[✅ Показать черновик] [Позже] [Не нужно]
```

«My move» is one of three honest forms: doing it now; it stands in the [Scheduler](SCHEDULER.md) under a named job and comes at a named time — said only while the Scheduler is passing on this machine; nothing is running. «Your move» is Mila's recommended step with two or three buttons, the recommended one first. The send guard checks the form before the message leaves; a promise with a time — «I will send it tomorrow», «I'll remind you at 18:00» — with no job in the Scheduler does not pass.

## Which word when
| The situation | The word |
|---|---|
| «Send this to the client from my name» | Lock → Consent |
| «Which of the three headlines?» | Choice |
| The owner is silent, and Mila must pick the order of her own work | Fork |
| The owner is silent, and the step costs money or goes outside | Lock: Mila waits and asks again, she does not go ahead |
| Any answer | The next move |

## In the plan
Not in the main branch yet, named here so the words do not surprise later: sending from the owner's personal Telegram account through the Lock (reading and drafts are in the core — `skills/shturman`); Mila's passport and checkpoints; wallets with spending through the Lock.

## In the code
| Part | File | Test |
|---|---|---|
| The consent proxy and its journal | `consent/consent_proxy.py` | `consent/test_consent.py` |
| Cards with options | `skills/cards` | `skills/cards/test_cards.py` |
| The fork journal | `skills/razvilki/scripts/razvilki.py` | `skills/razvilki/scripts/test_razvilki.py` |
| The next move in the send guard | `templates/home/.claude/hooks/send-guard.py` | `templates/home/.claude/hooks/test_next_move.py` |
| The four words in Mila's own canon | `canon/ZAMOK.md` | — |
