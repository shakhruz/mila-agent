---
name: talanty
description: "Use right after the connectors in the first days with a new owner, and on «what talents do you have», «what else can you do»: the core's queue of talents — Shturman (personal Telegram), then packs of the checked library — one card at a time, at most one a day, never at night; «Later» is a full answer. RU: таланты, «что ещё ты умеешь», очередь талантов после рождения."
---
# Таланты — что ещё я умею, по одному

`T=~/.claude/skills/talanty/scripts/talents.py`

Очередь — `talents.json` рядом (данные ядра): Штурман Telegram → Диагностика дела → Профориентация → Личный бренд → Курс по книге.
Талант-пак, которого нет в проверенной библиотеке этого ядра, хозяину не предлагаю; в `list` он помечен «нет в библиотеке».

## Когда
После коннекторов (слух, фантазия) — `python3 $T next --lang <язык>`. Ответ `id: null` — сегодня ничего не предлагаю (`why`
объясняет: ночь, нет ответа на прошлую, сутки ещё не прошли, предлагать нечего). Не обхожу эти правила словами.

## Карточка
- Штурман (`kind: skill`): отправляю `text` и `buttons` как есть (навык `cards`). «Подключить» → `python3 $T answer shturman connect`
  → дальше только карточка навыка `shturman` с тремя строками риска и его «да» там; одно нажатие ничего не подключает.
  «Позже» → `python3 $T answer shturman later`.
- Пак (`kind: pack`): `text`, `buttons` и метка — карточка библиотеки (`library.py offer`), как в навыке `library`.
  «✅ Поставить» → `python3 $T answer <id> connect`, потом установка по навыку `library` (`install-pack --library <id> --card …`);
  поставлен — `python3 $T done <id>`. «Не сейчас» → `python3 $T answer <id> later` и `library.py decline`.
«Позже» — полный ответ: сама больше не предлагаю (закон 6); попросит сам — `list` и карточка по его слову.

## Что не делаю
Не шлю две карточки талантов в один день и ни одной ночью. Не ставлю пак и не подключаю Штурмана без его нажатия.
