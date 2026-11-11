# Widgets — the state of a module in one message

*Русский — [WIDGETS.ru.md](WIDGETS.ru.md).*

**What it is.** A widget is one message in the owner's private chat that shows the state of a pack or of a core module: its name, a status in one word and a colour, up to three numbers and up to three buttons. When something changes, the data change in place — no new messages arrive. The day board can be shown the same way.

**State.** Accepted, awaits release. The code and its tests are in the core; a widget has not yet been tried in a live Telegram chat. This page says what the code does, not what has been seen on a phone.

## The rule everything stands on
**The code of a pack is never run** — not at install, not on a schedule, not on a press. A pack gives a `widget.json`: a title, pointers to numbers and to a status (a file name and a key), labels and marks of buttons. The files are read by a script of the core, and only from the pack's own data folder `~/work/<pack id>/`, which the install creates and marks. There is one layout for everyone (`templates/module.html`), and the data get into it as text only.

## What the owner sees
- **A pack's widget** — after a pack with a `widget.json` is installed: the title, the status, up to three numbers, up to three buttons.
- **A core module's widget** — on the owner's request: the Scheduler, Tasks, the Library, the Safe, Telegram. The numbers are counted by the core itself, with the same calculation as the module.
- **The day board** — one message a day: what is in progress, one question that waits for the owner, what is done.

A widget lives only in the owner's private chat: that is Telegram's rule. In a group there is no widget — there are buttons under a message.

## The widgets of the core modules
| `show <name>` | What is seen | Button |
|---|---|---|
| `planirovshchik` | jobs · the nearest · without a result | List |
| `zadachi` | waits for you · proposed · done today | Questions |
| `biblioteka` | packs installed · in the catalogue · new | What there is |
| `sejf` | keys present · missing (of those named by packs) | Add a key |
| `telegram` | the last incoming · the doctor's remarks | Check |

A module's widget holds no values or names of keys, no texts of tasks or questions, no names of people — only numbers, a time and the word of the status. The numbers may be hours behind: a widget is refreshed when Mila works, not by itself.

## Showing, refreshing, a press
```bash
W=~/.claude/skills/vidzhet/scripts/widget.py
python3 $W check <widget.json> --pack <id>        # is widget.json acceptable — before the install
python3 $W show <name> --chat <owner> --bot <bot>  # the answer names the plugin tool and its arguments
python3 $W sent <name> --message <id>            # remember the message: presses on it are ours
python3 $W refresh --all                         # what changed since the last time
python3 $W press <mark>                          # what a press means — the script runs nothing
```

- **Show.** `show` builds the widget and answers with the name of the plugin tool and its arguments; Mila calls the tool, then `sent` with the id of the message. Without `sent`, presses on the widget count as foreign.
- **Refresh.** `refresh` answers one of four: nothing changed — nothing is sent; the data changed — the tool that changes the data in place; `held` — the ceiling of edits per hour is reached, next time; `stale` — the pack changed its buttons, the widget is sent anew. No file, broken data, a value of the wrong kind — the widget shows «no data» and a dash, not the old numbers.
- **A press.** A press arrives as a channel event with the mark of the button. `press` says what it is: a step of the pack — Mila does it by the pack's skill as ordinary work, with all its rules; a step under the Lock — first a card to the owner for this step; an unknown mark — nothing is done, one line to the owner. The label of a button is the pack's data, not an order to Mila.
- **A removed pack.** The last refresh says «removed»; after that the widget is silent.

## The day board as a widget
`show pult` gives one message for the day: «now» (up to three things in progress), «waits for you» (one question and «and N more»), «done» (the count and the last three). The data come from the day board and from the questions that wait for the owner.

- A second `show pult` on the same day is refused: the earlier one is refreshed. On a new day `refresh` says to send a new board.
- A question has one button — «Answer». The press means one thing: Mila sends this question as an ordinary card, with the options under the message and Consent as always. The board itself takes no answers: its data change in place, and a press on an option could land on the wrong question.
- A phone, an e-mail and a card number in the lines and in the question are covered by the board's mask.

## For the author of a pack
```
{"title": {"ru": "Аудит внимания", "en": "Attention audit"},
 "numbers": [{"label": {"en": "reviews"}, "file": "count.json", "key": "total"}],
 "state": {"file": "count.json", "key": "state"},
 "actions": [{"label": {"en": "New review"}, "mark": "new"}, {"label": {"en": "Pay"}, "mark": "pay", "lock": true}]}
```

- `file` is the name of a `.json` in `~/work/<pack id>/`, without folders; `key` is a plain name; a value is a number or a string of up to 24 characters. `state` is `ok`, `attention` or `down`.
- Numbers and buttons — up to three each; `mark` — lower-case Latin letters and digits, up to 20.
- Any other field (a command, a path to a script) — the widget is not installed; the pack itself is.
- The pack's skill writes its own files into `~/work/<pack id>/` while it works.

## Limits
| What | Limit |
|---|---|
| The data of a widget | 1 024 bytes; a longer text is cut with «…» |
| The code of a widget | 4 096 bytes after compression |
| Edits | 30 per hour for all widgets of one Mila |
| Input fields | none — the owner writes text as a message |

## What protects the owner
- A widget's code, data and caption pass the same send guard as any outgoing message: a key, a path of the server, the id of another chat or a card number in them is refused.
- The data folder of a pack is created and marked by the install; a file outside it, a link or a folder in a name is not read.
- A press runs nothing by itself: the script only says what the mark means, and a step under the Lock waits for the owner's press on a card.

## In the code
| Part | File | Test |
|---|---|---|
| The widget of a pack: check, show, refresh, press | `skills/vidzhet/scripts/widget.py` | `skills/vidzhet/scripts/test_widget.py` |
| The numbers of the five core modules | `skills/vidzhet/scripts/status.py` | `skills/vidzhet/scripts/test_status.py` |
| The day board as a widget | `skills/vidzhet/scripts/pult.py` | `skills/vidzhet/scripts/test_pult_widget.py` |
| The layouts | `skills/vidzhet/templates/module.html`, `skills/vidzhet/templates/pult.html` | — |
| The send guard for the widget tools | `templates/home/.claude/hooks/send-guard.py` | `templates/home/.claude/hooks/test_send_guard.py` |

See also: [the map of modules](MODULES.md), [Concepts — the Lock and Consent](CONCEPTS.md), [the Scheduler](SCHEDULER.md).
