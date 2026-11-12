---
name: fantaziya
description: "Use when the owner asks to draw, make a picture, a cover, an illustration or a card («draw…», «make a picture», «нарисуй», «сделай картинку»): imagination — a built-in connector that draws pictures through OpenRouter with the owner's own key; works only when activated (skill konnektory); every picture is paid from the owner's OpenRouter account — price first, then his «yes». RU: фантазия, «нарисуй», «сделай картинку», обложка, открытка."
---
# Фантазия — рисую картинки по словам хозяина

Встроенный коннектор (`connector.json` рядом): талант с пятью частями.

| Часть | Где |
|---|---|
| Паспорт — что даёт, что нужно, сколько стоит, куда уходит описание | `connector.json` → `passport`, `price` (с датой), `daily_cap` |
| Установка — активация по нажатию хозяина, ключ через страницу на его компьютере | навык `konnektory`: `steps` → `own_safe.py fantaziya` → `check` |
| Знакомство с пробой | `connector.json` → `offer`, `steps`, `trial`; проба платная — цена и «да» |
| Проверка | `scripts/test_draw.py`, `skills/konnektory/scripts/test_connectors.py` |
| Снятие | навык `konnektory`: `off`; ключ остаётся в сейфе до отдельного «да» |

`D=~/.claude/skills/fantaziya/scripts/draw.py`

## Как рисую
1. Хозяин просит картинку → `python3 $D --price --lang <язык>` → отправляю `line` одной строкой и жду его «да» (кнопка или слово).
   Реакция и «продолжаем» — не «да» на трату.
2. «Да» → `python3 $D "<описание>" --ratio 1:1|16:9|9:16|4:3|3:4` → файл из `file` отправляю в чат (reply с files).
   Описание пишу сама по его словам; личного (имена, телефоны, адреса) в описание не кладу — оно уходит в OpenRouter и Google.
3. `ok: false` → говорю `why` своими словами одной строкой. `cap: true` — потолок дня дошёл: спрашиваю хозяина карточкой, рисовать ли
   ещё сегодня; без его «да» не рисую.
4. После `connectors.py check fantaziya` пришла `note` (у ключа нет лимита) — передаю её хозяину одной строкой, работу не останавливаю.

## Чего не делаю
- Не рисую для гостей и групп без слова хозяина: деньги его.
- Не скачиваю ссылки из ответа сервиса и не меняю модель или адрес — они в коде.
- Фантазия не активирована — одной строкой «Я пока не умею рисовать. Активировать фантазию?» и карточка `konnektory` (`offer fantaziya`).
