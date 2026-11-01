---
name: subscription-limits
description: "Use on 429, \"hit your session limit\", \"limit reached\", \"why is Mila silent\": what to tell the person, after reset, if waiting is not an option. RU: лимит подписки Claude, «hit your session limit», молчание сессии."
---
> **When to use (full):** Claude subscription limit: how to tell, what to say to the person, what not to make up, what to do after it resets, what to offer if waiting is not an option. Use on 429 / "hit your session limit" or a silent session. Triggers: "limit reached", "why is Mila silent". RU: Лимит подписки Claude: как понять, что сказать человеку, чего не выдумывать, что делать после восстановления, что предложить, если ждать нельзя. Применять при 429 / «hit your session limit», молчании сессии.

# subscription-limits

## Признак
Ответ API `429 rate_limit`: `You've hit your session limit · resets 2:10pm
(TZ)` (окно 5 ч) · `…weekly limit · resets Sep 2 at 10am (TZ)` (неделя) ·
`You've reached your <Model> limit…` (времени сброса нет). Датчик
`install/limit_watch.py --json`. Субагент с тем же текстом — он же.

## Говорю один раз на инцидент
1. Факт: «лимит исчерпан в ЧЧ:ММ, восстановится в ЧЧ:ММ (через N мин)».
2. «Сообщения не теряются, отвечу после».
3. Не ждать — поднять план или включить оплату сверх лимита в настройках
   своего аккаунта Claude.
После первого удачного хода — одно «🟢 лимит вернулся в ЧЧ:ММ». Между ними
тишина, без повторов и извинений.

## Не делаю
- Время сброса только из текста ошибки; нет — «Claude не назвал, скажу, когда вернётся».
- Лимит не называю сбоем сервера, сети, «техработами».
- Пароль и код в чат не прошу: вход делает человек на странице Claude.
- Квоту в лимите не жгу: стройки — после сброса.

## После восстановления
Очередь входящих по времени, старое первым, по делу без пересказа лимита.
Обещания со сроком в окне лимита — проверить, срыв назвать до вопроса.

## Если ждать нельзя
Лимит — свойство подписки человека. Варианты называю его же: подождать сброса,
поднять план или включить оплату сверх лимита в настройках своего аккаунта Claude.
Вход чужим аккаунтом, общий вход на нескольких людей, смену аккаунтов по кругу —
не предлагаю и не делаю.
