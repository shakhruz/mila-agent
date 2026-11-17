---
name: raspisanie
description: "Use instead of CronCreate whenever a job must run on schedule (daily check, reminder, weekly report): mila-cron writes it to the Mila's home so it survives a session restart. RU: «напоминай каждый день», «по понедельникам», «через неделю проверь», расписание, кроны."
---
> **When to use (full):** Schedule that does not get lost. A job set with CronCreate lives inside the Claude Code session and dies on restart, on image rollout and by itself after 7 days. mila-cron writes the job to ~/work/schedule/jobs.json in the Mila's home; the Scheduler (RU: «Планировщик») service outside the session reads it once a minute and puts the due job into the plugin journal as an event — the same road rituals and flywheel ticks take, so it reaches the session after any restart. RU: Расписание, которое не теряется: вместо CronCreate — mila-cron, задача в доме Милы, срок приходит событием службы «Планировщик».

# Расписание — mila-cron (не CronCreate)

Команды `mila-cron` в PATH нет: всегда `python3 ~/.claude/skills/raspisanie/mila_cron.py …` (ниже — `$M`). В событии Планировщика команда done/extend — уже с полным путём.

```bash
M=~/.claude/skills/raspisanie/mila_cron.py
python3 $M next "0 9 * * 1" 3                      # сначала проверить выражение: ближайшие сроки
python3 $M add otchet-pn "0 9 * * 1" "Понедельник: недельный отчёт владельцу"
python3 $M add vecher "30 19 * * *" "Вечерняя проверка" --by owner --word <чат>/<сообщение>
python3 $M list                                      # следующий срок, последний запуск, итог
python3 $M done otchet-pn "отправлен, 5 строк"       # итог последнего запуска
python3 $M pause|resume|rm <id> · extend <id> ГГГГ-ММ-ДД
python3 $M import ~/work/state/crons.md              # перенести кроны из снимка сессии
python3 $M import                                    # перенести кроны сессии из ~/work/.claude/scheduled_tasks.json (или import <файл.json>); повтор дублей не даёт
python3 $M add prodlit --at "2026-12-01 10:00" "Продлить домен"         # разовое дело на дату
python3 $M event vstrecha "2026-11-25 12:00" "Встреча с партнёром, офис" --prep 1d,2h   # событие хозяина + «будь готова»
python3 $M agenda --hours 24                         # повестка: события 📅, подготовка 🎒, задачи
python3 $M add sroki "0 * * * *" "Сроки дел" --check deadlines:work/sroki.json:3   # сначала проверка без модели
python3 $M start <id> "взялась" · fail <id> "почему"  # длинная задача: в работе / сорвано
```

## Правила
1. **Не CronCreate.** Любое «каждый день / по понедельникам / через неделю / в день встречи» — `python3 $M add` или `event`. CronCreate умирает с сессией.
2. **Сначала `python3 $M next`** — увидеть сроки глазами, потом `add`. Пояс — из USER.md хозяина.
3. **Не чаще раза в 5 минут**, задач до 1000, текст до 2000 знаков. Подписку тратят срабатывания, а не число задач: служба держит бюджет своих срабатываний в сутки.
4. **Срок жизни** — своим задачам 30 дней по умолчанию, максимум 90, дальше `extend` по событию «продлить?»; по просьбе хозяина или старшей (`--by owner|senior --word <чат>/<сообщение>`) — до 400 дней или `--no-expire` (задач без срока в доме — не больше 50).
5. **Регулярное, разовое, событие.** Регулярное — cron; разовое — `--at`; событие хозяина (встреча, эфир, поездка, продление) — `event`: сама встреча и точки «будь готова» заранее. Увидела событие в календаре или переписке хозяина, услышала от него — поставь его сразу.
6. **Будь готова.** Пришла точка подготовки — подумай, что хозяину подготовить, взять, доделать, что порекомендовать; готовы ли мы. Хозяину — коротко, с кнопками.
7. **Повестка перед глазами.** На старте сессии в контексте — повестка 24 ч; планируя день, смотри `agenda`, а не память.
8. **Дёшево, но качественно.** Задача, у которой часто нечего делать (сроки, новые файлы), — с `--check`: служба сначала проверит сама, без модели, и разбудит только когда есть дело.
9. **Пришло событие `[⏰ расписание] <id>`** — сделать дело и записать итог `done <id> "…"` (сорвалось — `fail <id> "почему"`; длинная задача — сразу `start`). Итог и срыв уходят в журнал дел. Нет итога за 2 ч (поле `dlit`) — строка сторожа исполнения. Тихие часы хозяина служба уважает сама.

Файл задач — только этим инструментом (атомарная запись под замком). Задача срабатывает, только пока служба проходит по этому дому: `python3 ~/.claude/hooks/doctor.py` показывает строку «Планировщик» — жёлтая значит «задачи стоят, служба не проходит». Состояние запусков ведёт служба «Сердцебиение» вне дома (в событиях и doctor она по-прежнему — «Планировщик»).
