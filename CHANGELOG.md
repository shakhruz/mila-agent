# CHANGELOG · Mila

## v1.7.9 · 12.11 — the v1.7.8 release with its release page

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Это тот же выпуск, что v1.7.8: у него появилась страница выпуска с проверенными файлами установки. Для вас ничего не меняется.

</details>

**For the owner**
- The same release as v1.7.8, now with its release page and verified install files. Nothing changes for you.

**For Milas**
- The update-plan test accepts Russian «Для хозяина» lines that name products and commands (Telegram, Claude Code, `mila onboard`): the text counts as Russian while Latin letters stay under a quarter. With v1.7.8 the test failed on the release commit itself, so the release page was never built.
- `tools/release.sh` runs the update-plan test once more after it raises `release.json` and before the commit and the tag; on a failure it restores `release.json` and stops.

## v1.7.8 · 12.11 — widgets and the day board, the next move, four words of the core, Shturman, the problem journal, a Scheduler that is confirmed, an honest doctor for a newborn

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Штурман (пробная версия): по вашему слову читаю ваш личный Telegram — каналы и открытые группы; личные чаты и закрытые группы — только те, что вы открыли сами, — и кладу черновики; отправляете вы. Подключаете сами, в терминале; отключить — одной командой. Живой вход ещё проверяется на тестовом аккаунте — подключайте, если готовы быть первыми.
- Развилки: когда вы молчите, я иду по своему рекомендуемому варианту только в собственной обратимой работе и записываю точку; выберете другое позже — вернусь к ней и переделаю. Деньги, отправка и публикация от вашего имени — по-прежнему только по вашей кнопке.
- Следующий ход: каждый мой ответ кончается двумя строками — что делаю я («Мой ход») и что советую вам («Ваш ход») с двумя-тремя кнопками; первая — рекомендуемая, нажали — делаю сразу. Обещаю «пришлю завтра» только тогда, когда это стоит в расписании.
- Планировщик на ноутбуке: установщик ставит проход раз в минуту — «напоминай по понедельникам» теперь срабатывает и там. Если служба у вас не работает, я не обещаю «придёт в 09:00», а говорю об этом прямо.
- Виджет пака: после установки пака с виджетом вы получаете одно сообщение — статус словом, две-три цифры и до трёх кнопок; цифры меняются на месте, без новых сообщений. Только в нашей личке. Код пака при этом не запускается.
- Пульт дня теперь у каждой Милы с рождения: одно закреплённое сообщение — что в работе, что ждёт вас, что сделано. Раньше он шёл только с паком «Бизнес-помощник».
- Журнал проблем: каждый сбой, который замечаю я или вы, записываю — что случилось, что исправлено, чем проверено. Третий повтор одной причины я закрываю не обещанием, а проверкой или настройкой. Спросите «что пошло не так» — отвечу из журнала.
- Сразу после установки доктор больше не пугает красным: пока Мила не родилась, он говорит одной строкой «ещё не родилась — запустите mila onboard».
- Обновление одной командой: если скачать новую версию не удалось, я говорю об этом и останавливаюсь — раньше в таком случае заново ставилась прежняя версия с надписью «готово».
- Установка говорит прямо: мои сторожа записываются в ваш общий Claude Code и работают во всех его сессиях на этом пользователе; чтобы держать меня отдельно — заведите мне отдельного пользователя компьютера.

</details>

**For the owner**
- Shturman (a trial version): on your word I read your personal Telegram — channels and public groups; personal chats and private groups — only those you opened yourself — and put drafts; you send. You connect it yourself, in a terminal; one command disconnects it. The live sign-in is still being checked on a test account — connect it if you are ready to be among the first.
- Forks: while you are silent I go ahead by my recommended option only on my own reversible work and log the point; pick another option later — I return to it and redo. Money, sending and publishing in your name — still only by your button.
- The next move: every answer of mine ends with two lines — what I am doing («My move») and what I suggest you do («Your move») with two or three buttons; the first is the recommended one, a tap and I do it at once. I promise «I'll send it tomorrow» only when it stands in the schedule.
- The Scheduler on a laptop: the installer sets a pass every minute — «remind me on Mondays» now fires there too. If the service is not running on your machine, I do not promise «it comes at 09:00»; I say so plainly.
- The pack widget: after a pack with a widget is installed you get one message — status in a word, two or three numbers and up to three buttons; the numbers change in place, no new messages. In our private chat only. The pack's code is not run for it.
- The day board is now inborn: one pinned message — what is in progress, what waits for you, what is done. It used to come only with the «Business assistant» pack.
- The problem journal: every slip that I notice or you point out is written down — what happened, what was fixed, how it was verified. A third repeat of one cause is closed with a check or a setting, not a promise. Ask «what went wrong» — I answer from the journal.
- Right after the install the doctor no longer frightens with red: until Mila is born it says one line — «not born yet, run mila onboard».
- The one-command update: if the new version cannot be downloaded I say so and stop — before, the old version was installed again and reported as done.
- The install says it plainly: my guards are written into your own Claude Code and work in every session of this user; to keep me apart, give me a separate user of the computer.

**For Milas**
- New skill `problemy` (`work/problemy.jsonl`, 600, append-only, number and line under one lock): found → cause → fix → verified → closed, each stage with evidence (the rules of `dela`); places and classes are closed lists; the verification is another pointer and later than the fix; the third case of one class in one place (a reopen and a new problem — one count) refuses a promise and writes the refusal; `itog`, `list --open`, `povtory`. The evening `self-check` asks whether the owner corrected Mila today.
- `problemy.py povtory` also lists a place with three or more cases of different classes in 14 days — a line to look at, not a refusal.
- Releases: the GitHub release with files (`get.sh` pinned to the tag and its commit, `SHA256SUMS`) is made by the workflow `release` on a pushed tag `vX.Y.Z`, through the gate `tools/release_gate.py` — annotated tag, commit on `main`, `release.json` and CHANGELOG agree, not withdrawn, a green `tests` run for exactly this commit, a valid signature when `main` lists signers. `tools/release.sh` cuts a release from `main` only and builds the files with the same builder (`tools/release_files.py`); `gh release create` by hand is no longer needed.
- `dela.py`: the «already written» check and the new line are under one lock — two writers at once never log one stage twice.
- New skill `shturman` — the owner's personal Telegram account, reading and drafts only, off until the owner signs in himself in a live terminal (`login`); personal chats and private groups only those he opened (`allow`: his own word, read from his account, fresh, used once); a draft only where he writes; no sending, deleting, editing, reactions or «mark as read» in the code — a test lists the names and runs every command on a fake client; a pause and a ceiling per hour; `revoke` signs out at Telegram and wipes the files (no network — a red mark in `status`). The session files live in a key place closed to the session's tools; `docs/THREAT-MODEL.md` says what this access is; the library is pinned with sums (`skills/shturman/requirements.txt`).
- The schedule service is called the Scheduler (RU: «Планировщик») in every text a person reads; file names and state paths keep the old name (`install/baraban.py`, `state/baraban`) — nothing to migrate.
- Four words of the core — Lock, Consent, Choice, Fork (`canon/ZAMOK.md`, `docs/CONSENT.md`). New skill `razvilki` (`work/razvilki.jsonl`): a fork point on Mila's own reversible work — what she chose, why, what to redo on a switch; `switch` by the owner's message, `done`; a point on anything behind a lock (money, sending, publishing, deleting, signing, «in his name») is refused by the mark and by the words, the refusal stays in the journal. `iniciativa`: silence is not consent — «while you are silent I do B on my side, nothing goes out».
- `razvilki`: «tell», «notify», «warn» a client, a partner or a guest (RU: сообщить, уведомить, предупредить) is a lock too — a fork on it is refused; the nouns («the client's message») are not.
- New inborn skill `sleduyushchij-hod` («the next move»): every answer to a person ends with «Мой ход: …» (doing now / stands in the Scheduler «job» and when it comes / nothing is running) and «Ваш ход: …» with 2–3 step buttons, the first one green. send-guard checks it on every reply: both lines last, the form, the job really in the schedule at the named time (`cronspec`), a promise with a time only with a job, no «nothing needed, moving on», no empty buttons; a part of a long answer ends with «(продолжение следует)». If the check itself breaks the answer goes out and the failure is written to `work/state/next-move-fail.jsonl` and the problem journal.
- New skill `vidzhet` (`widget.py check | show | sent | refresh | press`) — the «module widget»: one template for every pack (`skills/vidzhet/templates/module.html`, data drawn as text only), a pack gives `widget.json` — a title, pointers to numbers and a status (a `.json` file name and a key), button labels and marks; any other field (a command, a script path) — no widget. Values are read by the core script only from the pack's data folder `work/<pack id>/`, which `install-pack` creates and marks; a folder that was in the home before the pack, a link, a second name of another file, a key-like name give «no data». The script sends nothing itself: it prints what to call (`widget`, `widget_data` of the Telegram plugin); the same data — no call; one ceiling of edits per hour for all widgets. A press «[widget] w_<pack>_<mark>» → `press` says whose step it is; nothing is run, an action with `lock` goes through Consent. A pack's code is never run. `remove-pack` takes the pack's data folder away with it when nothing but the install mark is left there; a folder with data stays.
- Widgets of five core modules — `widget.py show planirovshchik | zadachi | biblioteka | sejf | telegram`: the numbers are counted by the core (`skills/vidzhet/scripts/status.py`) with the modules' own code (`mila_cron.listing`, `cards.deck`, `library.verified_index`, `vault.has`, the doctor's local checks); only numbers, times and a status word come out — never a key's value or name, a job's text, a question. A broken source is «no data». A pack with a core module's id gets no widget. A press names the core command Mila runs; the script runs nothing.
- `pult-dnya` (the day board) moved from the pack `business-assistant` into the core (`skills/pult-dnya`); the pack is 0.1.1 and lists it among the core skills it uses. `install-pack`: on a pack's update a skill of its previous version that has since become a core skill is not removed — the core carries it. `mila-update`: two steps within one second each keep their own backup (the second used to overwrite the first, and a rollback then had nothing to undo).
- The day board as a widget — `widget.py show pult`: one message a day (its own template `skills/vidzhet/templates/pult.html`, data from the day board and the inbox of questions): what is in progress, ONE question that waits for the owner with «and N more» and a single button «Answer», what is done. The press only asks Mila to send the question as a usual card — the widget takes no answers, so a tap can never land on another question after the data changed in place. A second board on the same day is refused (`refresh pult`; `--again` to resend); on a new day `refresh` asks for a new board.
- send-guard also checks the widget tools of the Telegram plugin (`widget`, `widget_data`): the widget's code, data and caption are read as one text — keys, server paths, other chats, a recipient that is not allowed; a card number inside a widget is refused (no mask there). `install.sh` and `hooks_sync.py` register the guard for these tools and move an older home's matcher.
- send-guard: a report with an apology passes only in the owner's chat and only when it names a problem number that is in `work/problemy.jsonl` (a whole «found» line: the fact and a pointer to evidence) and is open or was closed today; a number alone no longer opens the filter.
- The Scheduler is confirmed before it is promised. Every pass that has an owner leaves `<state>/<home>.beat` (`baraban.py`, `--beat-dir` for a root-run service); `cronspec.last_beat` finds it. send-guard lets «стоит в Планировщике» through only while the beat is fresher than five minutes — otherwise a refusal that says the Scheduler is not running; `doctor` has a «Scheduler» row (yellow: jobs set, the service is not passing). `install.sh` installs `baraban.py` and a per-minute timer (launchd `com.milagpt.scheduler`, systemd user `mila-scheduler`), and adds none where another Scheduler already passes for the home; `MILA_SKIP_TIMERS=1` writes the files without loading them. The pass runs with `-B`, and `install.sh` no longer takes `__pycache__` in a skill for the owner's change (a used skill was backed up on every re-install; two installs within one second failed on the backup). One time-zone rule, `cronspec.owner_tz` (the USER.md line, else Asia/Tashkent), for the service, `mila_cron.py` and send-guard — `mila_cron.py` no longer takes the machine's zone.
- Docs: an index of the pages (`docs/README.md`, `.ru.md`, linked from the four READMEs) and the first design page — Mila's passport (`docs/design/PASSPORT.md`, `.ru.md`), marked «in development» in its first lines: the key and the number, a quiet birth and the certificate, the twelve words, the recovery envelope, the archive, the fingerprint of state, rebirth, what is decided and what is open. The test: every page is in the index; a design page says it is not in the core and the map of modules agrees.
- Docs: the map of modules (`docs/MODULES.md`, `.ru.md`) — fifteen modules, each with what it gives, what it consists of and a state mark (in the core / accepted, awaits release / in development / as a pack); and Mind (`docs/MIND.md`, `.ru.md`) — three kinds of knowing, the constitution, the qualities, the habits. The test checks that every named path exists and the numbers equal the texts they point at.
- Docs: two new pages in two languages — the Scheduler (`docs/SCHEDULER.md`, `.ru.md`: setting a job, limits, missed slots, quiet hours, where the service runs — and that the laptop installer does not start it) and Concepts (`docs/CONCEPTS.md`, `.ru.md`: Lock, Consent, Choice, Fork, the next move). `tests/test_docs_pairs.py` keeps the two languages in step and the numbers equal to the code.
- `install.sh` runs under bash 3.2 (the system shell of macOS): the settings step is no longer a here-document inside `$( … )` — one unpaired apostrophe in a comment there ended the installer. `tests/test_bash32_heredoc.py` keeps such blocks out of the installer and paired in every other script.
- `MILA_SKIP_TIMERS=1` covers both timers of the installer — the hourly turns-collect job and the Scheduler: a trial install with a temporary HOME loads nothing and no longer takes down the machine's own job of the same name. `install/test_get.sh` sets it.
- `get.sh`: a failed fetch on update stops with a clear line (the shell used to go on and install the old version again); git's harmless «… is not a commit!» line on a clone by a release tag is dropped, every real git error and its exit code are kept; run by `get.sh`, `install.sh` does not print the «No Telegram plugin yet?» hint before the plugin is installed.
- `doctor`: a home with no token and nobody paired is «not born yet» (`"unborn": true` in `--json`, exit code 0) — the channel checks are not run; the installer creates the channel folder closed (700); a process whose home cannot be told is no longer taken for this home's (the daemon — by `receiver.pid` or its environment, on macOS read with `ps -E`), the hourly timer is «installed» only when the service points at this home, and a channel folder taken from `TELEGRAM_STATE_DIR` and lying outside the home is said so. New strings in the four dictionaries (uz and zh await a native reader).
- The Scheduler's widget says «down» when there are jobs and the service has left no fresh pass mark for this home.
- Docs: the Widgets page (`docs/WIDGETS.md`, `.ru.md`); the pairs test checks that the limits on the page are the limits in the code.
- `tests/run_all.sh` prints a failed test's own failure lines under it — a red run on a machine nobody can log into names the place by itself. `tools/kitchen_lint.py` also reports a reference to someone's say-so about an edit, in files and in commit messages.
- CI: the tests workflow runs on branch pushes and pull requests, not on tag pushes; the apt step no longer fails on a hung `apt-get update`.

## v1.7.7 · 10.11 — the pack library: free packs from Mila Library

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Библиотека бесплатных паков: после знакомства я предлагаю один пак под ваши слова — поставлю только по вашему нажатию; «Не сейчас» — больше не предложу. «Какие есть паки» — каталог.
- Первые четыре пака: «Бизнес-профиль», «Профориентация», «Аудит внимания», «Совет моделей».

</details>

**For the owner**
- The free pack library: after we get acquainted I offer one pack that fits what you told me — installed only when you press; «Not now» — I won't offer again. «What packs are there» — the catalog.
- The first four packs: Business profile, Career direction, Attention audit, Council of models.

**For Milas**
- `skills/library/library.py` (refresh, list, suggest, offer, decline, tutorial): the index of the mila-library repository is trusted only with the sha256 this release carries (`library.lock`: the index and the archives are read at the library's tag `core-v1.7.7`, never from a branch; empty — not connected); after onboarding one entry pack is offered from the categories «start» and «business», archives only with the index's sum; `update.py pack-plan/install-pack --library <id>` checks the chain again. `tools/build_library.py` builds the index (archives without install.sh; «for whom» ≤120 chars, no links, @, `, commands or imperatives). Removing a pack keeps the person's files (`PROFILE.md`).

## v1.7.6 · 10.11 — Mila Agent: one volume, keys and the owner's consents out of the session's home (security audit 09.11)

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Ключи и ваши согласия теперь хранятся отдельно от дома Милы: я пользуюсь ключом, но прочесть его не могу.
- На ноутбуке я чаще спрашиваю разрешения: вход на другие компьютеры (SSH), автозапуск, правки вне рабочей папки.
- Заново спрошу согласия на посты и траты; в облаке до обновления задайте id хозяина и том.

**Прочтите до обновления (облако: Railway, Hostinger, docker compose)**
- Теперь у Милы один том на /var/lib/mila: внутри дом, ключи и согласия. Railway: в настройках тома поменяйте Mount path на /var/lib/mila. compose: возьмите новый docker-compose.yml. Без тома Мила работает, но вход в подписку слетит при следующем развёртывании — об этом скажет карточка.
- Задайте OWNER_ID (ваш Telegram id) в переменных платформы: список владельцев после обновления не переносится. Без него хозяином не считается никто: кнопки «только хозяину» и согласия выключены, раз в день я напомню тому, с кем спарен бот.
- Согласия на действия от вашего имени (посты, траты) нужно дать заново — старые сохранены отдельно, но в работу не берутся.
- Если после обновления Мила молчит — посмотрите журнал контейнера, строки со словом mila-state: там сказано, что мешает старту.

**На ноутбуке**
- Новый пример прав спрашивает вас чаще: про SSH, файлы запуска оболочки, автозапуск и правки вне ~/work. Ваш permissions.json не меняется — сравните с новым примером.

</details>

**For the owner**
- Keys and your consents are kept apart from Mila's home: I can use a key, not read it.
- On a laptop I ask more often: signing in to other computers (SSH), autostart, edits outside the work folder.
- I'll ask again for your consents to posts and spending; in the cloud set OWNER_ID and the volume before the update.

**Read before the update (cloud: Railway, Hostinger, docker compose)**
- One volume at /var/lib/mila holds the home, the keys and the consents. Railway: set the volume's mount path to /var/lib/mila; compose: the new docker-compose.yml. Without it Mila runs, but a card says the sign-in will be lost at the next redeploy.
- Set OWNER_ID: the owners' list is not carried over. Without it nobody counts as the owner: owner-only buttons and consents are off, and once a day I remind the person the bot is paired with. Give consents again: old decisions are kept as evidence, not used.
- Mila silent after the update — look at the container's log, lines with mila-state: they say what stops the start.

**On a laptop**
- The new permissions example asks more often: SSH, shell start files, autostart and edits outside ~/work. Your own permissions.json is not changed — compare it with the new example.

**For Milas**
- `docker/mila_state.py` (root step instead of `chown -R`): moves an old volume-home into `home/` one rename at a time, owns folders by descriptor, renames Claude project folders to the new path, carries old `io/` journals only (decisions to `io/quarantine`). Key store `/var/lib/mila/keys`; `io/` at `/var/lib/mila/io`. No volume / no owner → a once-a-day line at session start asks Mila to tell the owner. An old Mila in the volume's root is told by `work/` or the `.mila-home` marker (now left in every home), not by `.claude`: a volume with plain Claude Code keeps its `.claude` where it is, Mila goes into `home/` beside it, a line says so. An empty `home/` next to an old home in the volume's root (a runtime makes the image's WORKDIR before the entrypoint) no longer hides the old home: it moves; a `home/` with files next to it stops the start with a line. The image's WORKDIR is `/` (outside the volume); `docker exec` lands in `/`.
- secret-guard: the key places (`~/.mila-auth`, the safe, the Telegram plugin's `.env`, `.credentials.json`) are checked by their real path for every reader — a link from `~/work` is the same file, a hard link is told by its inode, in a place's sub-folders too (a key with a second link closes lines-search), a path that cannot be resolved is refused; a Grep that prints lines over a folder holding one of them is refused (narrow the path or give a glob); file lists and counts pass. `permissions.example.json`: Grep and Glob get Read's deny rule.
- Key keeper: the store is `/var/lib/mila/keys`, outside the session's home; root moves old keys by descriptor, following no link and no hard link, and wipes through the same descriptor; a store of a foreign uid stops the start. A keeper that is on but did not start stops the start — keys never stay in the session's environment (the old way only by an explicit `MILA_KEYD=off`); one bad old key file skips that key, not the keeper. `/status` gives the bot's id only from a token of the checked shape.
- Start under root: the root step runs from `/` with `python3 -I` (a `json.py` in the session's home is never imported as root); a guard checks every root python line, setpriv bodies excepted. `io_perms` walks by descriptors — `io/` swapped for a link changes nothing; no `chmod -R` over the Telegram state; `io/` (consent journal, its key, the owners' list) is read-only to the session; `cards.jsonl` is made by descriptor.
- `permissions.example.json` (audit №14): SSH, shell start files, own programs, autostart, `.mcp.json`, `.git/hooks`, `.git/config` and `.claude/` anywhere — ask; a path with `..` — ask; a silent allow for Edit/MultiEdit/Write only inside `~/work`.
- Backup (audit №16): keys under key-named fields (JSON and env lines; the name split by `_`, `-` and case, a whole segment decides — `secretary`, `TOKENS_USED` stay) and Groq keys are cut from the copy; names stay; the report counts cuts by field name.
- Image and CI (audit №24): `.dockerignore` keeps `.git`, local secrets and build junk out of the image; every checkout without persisted credentials.

## v1.7.5 · 07.11 — the first start after an install opens a conversation

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Для новых установок: первый запуск больше не закрывается сразу — я начинаю новый разговор.

</details>

**For the owner**
- The first `mila` after an install no longer quits right after the trust questions: with no earlier conversation in that folder it starts a new one.

**For Milas**
- `install/mila`: no conversation for the current folder in `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<folder>/` — start without `--continue` (as `mila new`) and say so; otherwise `--continue` as before. `mila onboard` ends with «First start: mila new». `install/test_mila_first_run.sh`.

## v1.7.4 · 06.11 — a portrait when Mila is ready, a journal of the key guard's refusals, guards wired after an update

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- У новой Милы первое сообщение хозяину — с её портретом.
- Если сторож ключей подключён, он записывает каждый свой отказ — без текста команды и без самих ключей.
- Mila Agent: страница подключения бота показывает, как я просыпаюсь.

</details>

**For the owner**
- A new Mila's first message to her owner comes with her portrait (after `mila onboard` on a laptop, after the Claude sign-in in Mila Agent).
- Where the key guard is wired, it keeps a journal of what it refused and why — never the command, never a value.
- Mila Agent: the bot-token page shows Mila waking up.

**For Milas**
- `tools/hooks_sync.py --guards`: registers the hooks an update delivers but never wires — send-guard, done-guard (and on failure, Claude Code ≥ 2.1.295), secret-guard with its deny rules, skill-hint, pd-mask, crons-keeper, reply-required — the way `install.sh` does; only what is missing, a backup of settings.json first.
- secret-guard: `~/.claude/mila-guard/secret-guard.jsonl` (700/600) — time, tool, rule, what matched.
- `install/onboard.py` step 3 and `docker/claude_login.py` «done»: sendPhoto with `docs/assets/mila-agent-hero.png`, the same words; no picture or Telegram says no — the text as before.
- `docker/token_page.py`: the «done» screen — Mila wakes up (SVG and CSS, no script).
- README: the superheroine in a round frame; the version badge reads tags.

## v1.7.3 · 06.11 — the channel check runs again after an update

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Проверка канала снова запускается после обновления: её переводы теперь приходят вместе с ней.

</details>

**For the owner**
- The channel check (doctor) runs again after an update: its translations now come with it.

**For Milas**
- `release.json`: a zone «переводы хуков (doctor)» — `install/locales/*.json` → `{claude}/hooks/locales/`. An update from v1.7.2 or older brought `doctor.py` without them and it stopped with a traceback. `test_clean_home.sh` runs doctor from the updated home.

## v1.7.2 · 06.11 — a smaller core with packs, consent before outside actions, strangers kept out of the session, the archive

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- В ядре теперь 34 навыка, остальные стали паками. Те, что у вас уже есть, остаются, но обновляются только вместе с паком. Паки: Менеджер, Контент, Реклама, Почта, Узбекский, Дом, Jev, Картинки, Бизнес-помощник. Навыки, ушедшие в паки, у вашей Милы остаются, но обновляются только вместе с паком. Знакомство — три вопроса и одна польза, без списка шагов и строки «⛽». Ядро работает только на Claude (ваша подписка или ключ Anthropic).
- После обновления образа чужие люди в группах до меня не доходят: я знаю только, сколько их написало. Это все, кроме вас и вашей команды. В Mila Agent им может коротко ответить отдельный помощник без инструментов, только по файлам, которые вы для этого положили.
- Mila Agent: пост, платная генерация, сообщение от вашего бота — только после вашего нажатия на карточке в личке, где виден весь текст и куда он уйдёт. «Нет» держится сутки; молчание — не согласие; ночью карточка ждёт утра.
- Mila Agent: архив переписки — все сообщения подключённых чатов и файлы; читает его только приёмник, не я. Группа узнаёт об архиве одной строкой.
- После обновления образа голосовое от чужого человека не скачивается и не расшифровывается; 👀 ставлю только после того, как сообщение записано.
- Токен вашего бота в Mila Agent — тоже у хранителя ключей: Мила пишет в Telegram через него и не может прочитать токен.
- Ваш токен Claude и ключи голоса в Mila Agent теперь у хранителя ключей — отдельного пользователя в контейнере: я пользуюсь ими, но прочитать их не могу ни я, ни подсказка-инъекция.
- Mila Agent после обновления образа: новые навыки и мой новый CLAUDE.md доходят до уже живущей Милы (раньше — только до новой); ваши правки в CLAUDE.md и конституции не затираются — новая версия ляжет рядом; неизменённая конституция при новом образе обновляется (образ обновляете вы сами). После перезапуска я продолжаю разговор, а не здороваюсь заново.
- Знакомство без кнопки «Удиви меня»: разбор вашего сайта или канала — шагом д2 в блоке «Ваше дело», одна находка и один шаг.
- Паки: «поставь пак …» или архив пака в личку — показываю название, версию, новые навыки, нужные ключи и файлы с кодом; ставлю только после вашего «да». Новая версия архивом — обновление; «убери пак» и «откати» — назад, бэкап остаётся.
- Новое базовое качество №11 «Поднимаю вибрации»: я выбираю слова, от которых у вас прибавляется уверенности и силы, ничего не придумываю, а риск называю сразу с шагом, как его пройти.
- Все качества Милы — одним списком в `canon/QUALITIES.md`; новое №19 — «Деловое любопытство»: знаю рынок, цены и конкурентов и могу дать сравнение со свежими фактами.

- Конституция v2.2: в шапке — закон 4 утверждён владельцем 15.10.2026; текст законов не менялся.

- Новый навык «Учёт дел»: каждое дело — строкой с уликой (сделала, приняли, результат); итог по типам — только числа.

- «Сделала» — только после результата: если в одном ходу с командой я пишу вам «готово», а команда ещё не вернулась, сообщение не уходит; если команда упала после уже ушедшего «готово», я сразу присылаю поправку.

</details>

**For the owner**
- Mila Agent: a post, a paid generation, a message from your bot — only after your press on a card in your private chat that shows the whole text and where it goes. A «no» holds for a day; silence is not consent; at night the card waits for the morning.
- After the image update, in groups strangers (not you, not your team) do not reach me: I only learn how many wrote. In Mila Agent a separate helper with no tools may answer them briefly, only from files you put there for that.
- Mila Agent: an archive of every message and file in connected chats; only the receiver reads it, not me. A group is told about it in one line.
- After the image update, a stranger's voice note is not downloaded or transcribed; the 👀 comes only after the message is written down.
- Telegram: Mila can pin a message and work with forum topics — answer in the topic a message came from, open a topic for a task and close it when it is done.
- Mila Agent: the part that hears Telegram works under its own user — what people wrote and which buttons you pressed is kept where Mila can read but not rewrite; every message is marked by who wrote it (you, your team, someone else) by Telegram id, not by name.
- A smaller core: 34 skills instead of 74; the rest are packs installed by your «yes» (Manager, Content, Ads, Mail, Uzbek, Home, Jev, Images, Business assistant). Getting acquainted is three questions and one benefit — no step list, no «⛽» line. The core runs only on Claude (your subscription or Anthropic key).
- Your Claude token and voice keys in Mila Agent are now with the key keeper — a separate user in the container: I use them, but neither I nor an injected prompt can read them.
- Mila Agent after an image update: new skills and my new CLAUDE.md reach a Mila that already lives (before — only a new one); your edits to CLAUDE.md and the constitution are kept — the new version goes beside them; an unedited constitution is updated with a new image (you redeploy it yourself). After a restart I continue the conversation instead of greeting you again.
- Getting acquainted without the «Surprise me» button: the look at your website or channel is step д2 in the «Your business» block — one finding and one step.
- Packs: «install the pack …» or a pack archive in a DM — I show the name, version, new skills, keys it needs and its code files, and install only after your «yes». A newer archive updates it; «remove the pack» and «roll back» take it back, a backup stays.
- New core quality №11 «I raise the spirit»: I pick words that add confidence and strength, make nothing up, and name a risk together with the step through it.
- All of Mila's qualities in one list: `canon/QUALITIES.md`; new №19 «Business curiosity»: I follow the market, prices and competitors and can give a comparison with fresh facts.

**For Milas**
- Groups: owner / team / stranger by Telegram id; strangers go to `guests.jsonl` (0600), the session gets `guests_since_last` and a placeholder for a quoted stranger; the strangers' lane `mila-guest` (uid 1004) with no tools, its own key and limits. On by default and always in Mila Agent; `TELEGRAM_SAFE_GROUPS=0` turns it off elsewhere (a Mila serving customers in groups with no team list). See docs/SAFE-GROUPS.md.
- Journals: voice is transcribed only after the access check; the journal is written before the ack; one envelope builder (`install/envelope.py`) for the feeder and the hook. See docs/JOURNALS.md.
- Consent proxy (`consent/`, user `mila-io`): cards drawn by the proxy, a signed press, a hash-chained `decisions.jsonl`, «no» for a day, quiet hours, at most 10 cards an hour, standing permissions up to 7 days and $10 a day; `bot-send`, `spend`, packs and core updates ask through it where `mila-io` exists. See docs/CONSENT.md.
- Archive (plugin; Mila Agent or `TELEGRAM_ARCHIVE=1`): `io/archive/<chat>/<YYYY-MM>.jsonl` 0600 in a 0700 folder, edits as their own lines, file originals by sha256 under a ceiling (`ARCHIVE_FILES_MB`), observer groups keep strangers as metadata only; outgoing messages through the key keeper's spool folder (a file per send, emptied by the receiver). See docs/ARCHIVE.md.
- mila-update: a snapshot before every apply (`backups/<time>-<tag>-snapshot.json`, 600) — mila-cron job ids, session crons, settings.json hooks (event and file name only, no env), skills (sha of SKILL.md); no values or texts. `health` names what disappeared after the update.
- skill-hint (`templates/home/.claude/hooks/skill-hint.py`, UserPromptSubmit): a message from the owner (terminal or the owner's private chat) that is exactly one word from the map («пульт», «входящие», «расписание»…) adds «call skill X» to the turn, only if that skill is installed; groups and other people get nothing. Each Mila adds her own words in `~/.claude/skill-hints.json`.
- Plugin tools `pin` (pin/unpin, silent by default) and `topic` (list, create, rename, close, reopen; no delete); `reply` takes `thread_id`; inbound from a topic carries `thread_id` and `topic`; `topics.json` registry kept from Telegram's service events, shared by the session's folder and the receiver's through a link (entrypoint).
- Mila Agent: the receiver runs as its own OS user `mila-io` (1003, group `agent`), started by the root step after the session's «go» (`telegram/receiver.go`). Journals it alone writes — inbound, presses (`taps.jsonl` with the card text Telegram showed), authorizations, suspicious — live in `telegram/io/` (`mila-io:agent 2750`, files 0640); the session reads them, cannot write them; links keep the old paths. Where a `mila-io` user exists (by `/etc/passwd`, not a variable), `update.py`, `spend.py` and the feeder read presses, owners and inbound only from `io/` owned by `mila-io`, no fallback; owners live in `io/owners.json` (from the platform's `OWNER_ID`/`OWNERS`, or once at the first «go»), never from `access.json`. Every event carries `from` (owner/team/other by Telegram id); the feeder passes `from`, `user_id`, `type`, `observe_only`, `chat_type`, `chat_title` into the envelope, and `reply-required` no longer asks to answer observer messages and reactions. The key keeper also listens on `/run/mila-keyd/api.sock` and gives `getUpdates`/`deleteWebhook` only to `mila-io` once the receiver is up. See docs/RECEIVER-AND-JOURNALS.md.
- Mila Agent: a press on a card Mila sent (packs, spend, any `choice` button) reached the receiver, which looked in its own `cards.jsonl` while the session had written the card to `telegram-session/cards.jsonl` — «button not found». One shared file now (a link; earlier cards move over once), and scripts in the session read the receiver's journals through `MILA_TG_STATE`.
- The bot token joins the key keeper: route `/telegram/bot…/<method>` and `/telegram/file/bot…/` — the keeper puts the real token into the path; `setWebhook`, `logOut`, `close` are refused. The entrypoint moves `TELEGRAM_BOT_TOKEN` and `~/.mila-auth/bot_token` (token page, birth code) into it and exports `TELEGRAM_API_ROOT=$MILA_KEYD/telegram` with a placeholder token `<bot id>:mila-keyd-placeholder-not-a-token`; the plugin (pinned to its commit with `TELEGRAM_API_ROOT`) and every core helper that calls Telegram honour it.
- Skills moved out of `skills/` into `packs/<pack>/` (40): manager (client-chat, guest-path, lead-qualify, crm-dialogs, dialog-close, reply-from-examples, bot-send, draft-and-check, polite-no, exam), content-expert (infographic, live-frames, mini-podcast, video-overview, stilnaya, design-gates, flashcards, youtube-research, visual, mila-stickers, humanizer-ru), reklama, pochta, uzbek, dom (alisa-connect, screen, tastes), jev, kartinki (model-choice, spend), owner-telegram (+own-inbox), business-assistant (plan-fakt, pult-dnya, bud-gotova, questions, razbor-lichki, zhonglyor, mila-path). `pack.json` `needs_packs` names packs a role relies on. An update never removes a skill a home already has; a moved skill stays in a living Mila's home but is no longer updated from the core until its pack is installed. `update.py install-pack` also takes the Market's archive (`tools/pack_mila.py`: manifest.json with sha256 of every file — a changed or extra file refuses the pack). Onboarding: one short SKILL.md; `fuel.sh`, the cards, greetings and the ⛽ line removed; `OPENROUTER_API_KEY` gone from compose, entrypoint and the Hostinger page.
- Key keeper `docker/mila_keyd.py` (user `mila-keys`, uid 1002): the entrypoint's root step moves the Claude token and Deepgram/Groq keys (variables, `~/.mila-auth/oauth_token`, `~/work/secrets/*.env`) into `~/.keys` (700), wipes the old files, starts the keeper as that user and drops the variables; the session gets `ANTHROPIC_BASE_URL=$MILA_KEYD/anthropic` and a placeholder. Routes `/anthropic` (subscription: Bearer + `oauth-2025-04-20` beta; API key: `x-api-key`), `/deepgram`, `/groq`, `/status` (yes/no + sub/key). Keys go in through a write-only unix socket (`claude_login.py`, `key_page.py`). Streams are passed as they come. `docker/wall_probe.sh` in CI. `MILA_KEYD=off` — the old way.
- Mila Agent: `install.sh` runs again whenever the image's kit changed (sum of skills/templates/install in `~/.claude/.mila-agent-installed`); `install/home_template.py` updates `~/work/CLAUDE.md` and `canon/CONSTITUTION*.md` when the home has a version we shipped (`templates/work/SHIPPED.sha256`, old one kept as `.bak-`), else puts `*.new` beside; USER.md only when missing. The session restarts with `--continue`; a continued session that dies within 30 s starts fresh next time.
- Skill `packs` + `update.py packs | pack-plan | install-pack | remove-pack`: a pack (role + own skills) from the kit's `packs/` or from a .zip/.tar.gz the owner sent in a private chat. The archive is taken by `--msg <message_id>` from the receiver's journal (`inbound/events.jsonl`) — only from the owner's private chat — and downloaded by its `file_id`; no path from the model. Install and remove need the owner's press: `--card <card_id>` — a card in the owner's private chat with the pack's mark (`#pack-<sha16>` / `#pack-<id>-<version>` / `#unpack-<id>`), pressed «pack:yes» by the owner (cards.jsonl, events.jsonl), not older than 30 minutes, used once; a `--yes` string only by hand in a terminal. Before the press nothing goes into the home: the plan clips the pack's texts to one short line each (data, not instructions). Archive checks: paths inside the pack, no links or special files, no secret-named files, no executable bits, ≤300 files, ≤10 MB. A pack skill named like a core or separately installed skill is refused. The role is read through `~/work/PACKS.md` (one `@PACKS.md` line added to the home's CLAUDE.md). An update removes the skills the old version added and the new one lacks; `rollback` returns the previous version.
- The schedule in the container: Baraban ticks once a minute for the container's own home (`~/state/baraban`), so mila-cron jobs — «remind me in an hour», the morning summary — fire in Mila Agent too, not only on hosted servers. The owner is read on every tick, so pairing by a code after start needs no restart; the error log keeps its last 32–64 KB.
- secret-guard (`templates/home/.claude/hooks/secret-guard.py`, PreToolUse on Bash/Read/Grep/Glob/Edit/Write): the model does not read the owner's sign-in token (`~/.mila-auth`), the safe (`~/work/secrets`), another process's environment or a full environment dump with its own tools; helpers that use a key at the moment of the action are allowed. Plus deny rules `Read/Edit(~/.mila-auth/**)` and `(~/work/secrets/**)` — they hold even in the container's skip-permissions mode. A layer, not a wall: the model can technically still read the token (a path mask or a variable name in parts gets past the hook); the wall is `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`, which needs bubblewrap and waits for a probe on Railway.
- A newborn's first talk is short and honest: who you are, what you do, what hurts — no step list, no progress line; money only as fact (your Claude subscription or Anthropic key — `fuel.sh` now sees a setup-token subscription and an API key); no «trial reserve from us» anywhere in the onboarding skill; a Latin name in a Russian talk — Mila asks how to address you; formal «вы» after sign-in in every language.
- Voice in the container: the receiver runs `install/transcribe-voice.sh` for every voice note — Deepgram nova-3 (language=multi) first, Groq whisper second (Uzbek: Deepgram has none; Groq is used when Deepgram is unsure and a Groq key is there). Keys from env or `~/work/secrets/<deepgram|groq>.env`; Mila gets them through a one-time page (`docker/key_page.py deepgram|groq`, a link on the platform's public address, 10 minutes, the key checked with the service, 600) — never through the chat.
- Language of a newcomer: the inbound envelope carries `lang=` (the sender's Telegram language) when the plugin passes it; a newborn answers in it before the first written word, then in the language of the last message, English if unknown; no language buttons.
- A newborn's home: `templates/work/CLAUDE.md` and `USER.md`, the constitution in `~/work/canon/`. Without them a fresh Mila Agent answered «How can I help?» like a plain Claude; now the first talk is getting acquainted (the `onboarding` skill), in the owner's language. install.sh and the container's start add only what is missing.
- One field, once (`docker/token_page.py`): a container with no bot token and a platform port (`$PORT`, Railway and similar) opens a small page — Mila's face, greetings in several languages, English by default, the browser's language if known, nothing loaded from outside. The person pastes the token from @BotFather, Telegram confirms it (getMe), the token is saved in the volume (600) and the page closes for good. The owner is whoever opens the one-time link `t.me/<bot>?start=pair_<code>` shown on the page. The page lives 30 minutes after start, 5 attempts per address and 20 in total; restart opens a new window. BIRTH_CODE and TELEGRAM_BOT_TOKEN still work.
- done-guard (`templates/home/.claude/hooks/done-guard.py`): a `PreToolUse` hook on `reply`/`edit_message` denies a «done» text while a work call of the same model message has no result yet; a `PostToolUseFailure` hook tells the model to send a correction when a call failed after a «done» reply of the same message had already left. Fail open, a short word list; it catches the model's mistakes, not a hostile sender.
- Mila Agent in one container: `docker-compose.yml`, `docker/` (Claude Code, the kit, the mila-telegram plugin as a development channel, receiver + session in tmux, healthcheck), `docs/DEPLOY-HOSTINGER.md`, GitHub Action `agent-image` (publishes to GHCR only on `v*` tags). Inside the container permissions are not asked — the threat model has a «one-container setup» section. `CLAUDE_CODE_VERSION` in the Dockerfile is pinned to the version README calls tested; the maintainer raises both together.
- Sign in to Claude from Telegram (`docker/claude_login.py`): a container with no Claude login does not wait forever — it answers /start with Anthropic's own sign-in link (`claude setup-token` in a pseudo-terminal), takes the code back in the chat, deletes that message, keeps the token in the volume (600) and starts the session; the owner is OWNER_ID, the owner id of a birth code, or whoever sends the pairing code printed in the container's log (`/pair CODE`); the sign-in code is accepted only from the owner's private chat while that setup-token is alive (10 min). No ports, no page.
- Birth code (`docker/birth_claim.py`): a container started with only `BIRTH_CODE=MILA-XXXX-XXXX-XXXX` fetches its bot token (and the owner's id) once from the birth relay over https and keeps it in the volume (600); the person never copies a bot token.
- Baraban: the schedule service outside the session — mila-cron jobs keep running when the session is down; files in a Mila's home are opened component by component without following links.
- `mila-update` fleet plan (`fleet_plan.py`): one read-only table before rolling an update out to many homes; started from root, it reads each home with that home owner's rights.
- `cards`: a variant label longer than 40 characters is refused with a reason instead of being cut.
- Safe as a module (`skills/safe-link/scripts/vault.py`): whether a key is in place (environment first, then the safe file) and whether the provider accepts it — OpenRouter, Groq, the bot token; the value is never printed, and the OpenRouter key limit is named a limit, not a balance.
- `key_in_chat.py`: tells the kind of a key in a text and where to reissue it, never the value; `redact()` gives a text without it. Not wired into the inbound path: what keeps a key in a person's message from the model is the receiver's `maskSecrets`.
- New skill `dela` (quality «remembers every deed»): each real piece of work goes to `work/dela.jsonl` with evidence — done, taken by the person, result; a pointer, never the chat text; refused without evidence, with personal data or with a generic name like «post». `dela.py itog` gives counts by type, cumulative (done ≥ taken ≥ result).
- Delivery journal for core scripts (`install/tg_delivery.py`): heartbeat and bot_send write the same journal as the mila-telegram plugin — did each message reach the chat, and Telegram's own reason if not; chat ids are salted hashes, no message text. bot_send now reports a network error as «not delivered» for that recipient instead of stopping the whole broadcast.
- Hearing and fuel read the key from the safe file (`work/secrets/groq.env`, `openrouter.env`, 600) when the environment has none; `docker-compose.yml` passes `GROQ_API_KEY`; SAFE docs say how to hand a key over until the own safe ships.

- Constitution v2.2: the header now says law 4 was approved by the owner on 15.10.2026; the text of the laws is unchanged (law 4 has matched the fleet word for word since 28.10).

**For maintainers**
- Tests run on macOS and Python 3.14 too (short socket paths, the design-gates test takes Arial Bold from the system).
- README: a shorter comparison table — rows with «no data» and the price line removed; a neutral grey «built on Claude Code» badge.

## v1.7.1 · 01.11 — stricter permissions and send checks, the whole text on the consent card, moving from OpenClaw or Hermes

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Файлы, которые я прикладываю к ответу, проверяются так же, как текст: ключ или служебный файл сторож отправки остановит.
- Где согласие на публикацию идёт через карточку «Публикуем?» (в облаке), на ней теперь весь текст поста, а не начало и конец.
- Переезд с OpenClaw или Hermes: память, навыки и «кто я» вашего прежнего агента переносятся в одну папку, разбираем вместе по одному куску.

</details>

**For the owner**
- Files I attach to a reply are checked like the text: the send-guard stops a key or a service file.
- Where a post goes out through the «Publish?» consent card (in the cloud), the card now shows the whole text, not its start and end.
- Moving from OpenClaw or Hermes: your previous agent's memory, skills and persona move into one folder, and we go through it together, piece by piece.

**For Milas**
- `install/permissions.example.json`: Edit/MultiEdit ask on the agent's own wiring (hooks, settings, channels, access.json, permissions.json, .env) like Write; the read-only shell is allowed only as a whole command — safe `git` subcommands without output, config or external programs, no recursion (`rg` always asks), paths only inside `work`, no other program named in the arguments; key files, the `secrets` folder and `/proc/*/environ` are denied to readers and to Read. `tests/test_permissions_example.py` runs 85 cases through the plugin's engine. Existing homes keep their own `permissions.json` (install never overwrites it) — compare with the new example.
- Send-guard: `files` of a reply — only regular files inside the home or temp, never keys or the agent's wiring, and a text file with a key inside is stopped; with no `OWNER_ID` and an unreadable `access.json` nothing goes out. The threat model says the guard covers `reply`/`edit_message` only.
- Consent proxy: the card shows the whole text (a long one in parts before the card; a part not delivered → no card); a payload may carry only `text`, `targets`, `when`, `attachments` (a category can narrow it); the socket appears only once it listens, with its final mode.
- `tools/import_agent.py openclaw|hermes` + skill `import-review`: persona, memory and skills into `~/work/imported/<date>-<kind>/` with a report; keys and sessions never copied; secrets stop a file; order-like lines stay data; personal data as labels; `undo`.
- README: no hard-coded «latest» version (the test forbids it), checksum lines for Linux and macOS, what the install changes on the machine, a paid plan, which login for a Mila that serves other people; internal pages out of the public repo.
- `tools/check_install_link.py` (+ a daily workflow): the README install command answers 200. CI runs the tests on macOS too; `run_ci_local` and `vault-link` without GNU-only commands.

## v1.7.0 · 31.10 — install from a release, English where a reviewer looks first, the personal Telegram as an opt-in pack

<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Обновление ставит себя новой программой из выпуска: старая больше не сможет поставить половину и записать новую версию.
- Открытое ядро стало чище: в публичных файлах нет внутренних пометок команды; в корне — инструкция для Claude Code, как поставить Милу человеку.
- Ночное обновление считает себя успешным только по явному «готово» от новой программы — иначе честно пишет «не поставлено», версия прежняя.
- «Личка хозяина» (ваш личный Telegram) больше не ставится с ядром — это отдельный пакет по вашему желанию; у кого она уже стоит, остаётся как есть.

</details>

**For the owner**
- The update installs itself with the release's own program: an old one can no longer install half and record the new version.
- The open core is cleaner: no internal team marks in public files; at the root, instructions for Claude Code on how to install Mila for a person.
- The nightly update counts itself successful only on an explicit «done» from the new program — otherwise it honestly says «not installed» and the version stays.
- «The owner's DMs» (your personal Telegram) no longer comes with the core — it is a separate opt-in pack; where it is already installed, it stays as it is.

**For Milas**
- `mila-update apply` (and the nightly auto-patch) run the release's own `update.py` when it is newer — only after the manifest check, only a regular file listed in the manifest, forward only, once.
- `tools/kitchen_lint.py` (in run_all): no internal task codes, message numbers or review times in public files; «owner's word» reads «owner's consent»; tasks live in `~/work/tasks` (`MILA_TASKS_DIR`, `MILA_TASK_PY` for another layout).
- `CLAUDE.md` at the root; README: «Mila Agent — the open-source business agent for Telegram».
- Nightly auto-patch installs with the release's own updater too and trusts only an explicit `"ok": true` from `apply`; anything else is «rejected», the version stays.
- README comparison: every cell links to its source or says «no data».
- `tools/kitchen_lint.py --log A..B` checks commit messages of a range before a push (history is public).
- Tests clean up after themselves: every shell test removes its sandbox, `run_all` gives each test its own `TMPDIR` — a full run leaves nothing in `/tmp`.
- Install from a release, not from `main`: the command is `…/releases/latest/download/get.sh`; `tools/release.sh` writes `SHA256SUMS` with the asset names (`sha256sum -c --ignore-missing`) and prints the `gh release create … install/get.sh SHA256SUMS` step.
- `owner-telegram` moved to `packs/owner-telegram` — an opt-in add-on (`"kind": "addon"` in `pack.json`: only its skills are installed, ROLE.md and CLAUDE.md stay); its README says what the user session can do and where its files are. Homes that have it keep their copy; the core no longer updates it.
- `docs/THREAT-MODEL.md`: inputs besides text (attachments, links, mail, files), a table «action → which layer stops it» with the laptop column, where each secret lives; «secrets out of the chat» no longer reads as «out of reach».
- English at the root and in `.github/`: the constitution's translation (`CONSTITUTION.en.md`, the Russian text stays the one Milas read), Code of Conduct (Russian beside it), issue/PR templates, CI comments; CHANGELOG owner notes in English with the Russian kept collapsed for installed updaters. `check_frontmatter` also checks `packs/`.

## v1.6.6 · 30.10 — your own pages on the screen, help with your personal Telegram, small updates by yourself
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Мила показывает на вашем экране свои страницы — игру, слайды, квиз, — без помощи администратора.
- Новая сила «Личка хозяина»: Мила разбирает ваш личный Telegram, кладёт черновики вашим голосом и ставит лайк на «спасибо» — только по вашему слову; отправляете всегда вы.
- Скажете «мелкие обновления ставь сама» — Мила будет ставить исправления ночью сама; новые версии и правку конституции — только по вашей кнопке. Карточка обновления одна: новая заменяет прошлую.

</details>

**For the owner**
- Mila shows her own pages on your screen — a game, slides, a quiz — without the administrator's help.
- New power «The owner's DMs»: Mila sorts your personal Telegram, leaves drafts in your voice and likes a «thank you» — only on your word; you always send yourself.
- Say «install small updates yourself» — Mila installs fixes at night; new versions and constitution changes only by your button. One update card: a new one replaces the last.

**For Milas**
- `screen page put/show/list/rm` — own HTML page on own screen; the hub serves pages from a separate host under a CSP sandbox.
- `mila-update`: a new offer says it replaces the previous one; `apply` refuses a tag older than offered (`--force-stale` by hand); `plan --offer` for manual cards; `auto=patch` — same x.y, risk ≤ medium, no constitution/canon change.
- `owner-telegram` (new): the owner's personal Telegram — read, draft in his voice, reaction by his word (emoji whitelist, private allowed chats; the word is his real fresh message to Mila's bot, single use); `draft-clear` erases only Mila's own draft, his only by a reply to her proposal. `own-inbox` (new): Mila's own account, answers as herself. `owner-dm` links to `owner-telegram`. Tests run without the core clone.
- `bot-send`: broadcast buttons the service would drop silently (not https, choice, row > 3, rows > 6, label > 40) are refused before the request, with reasons.
- `milagpt-chat`: the reply tool's button format `{label, choice|url, style}` (Bot API `{text, callback_data}` does not work); `tg.py` escapes «\» for MarkdownV2 and drops `\x00` from input.
- `pult-dnya`: one button per «waiting for you» item; a changed set of waiting items means a new pinned board (edit_message keeps the old buttons).
- `jev skill`: Jev picks from the whole catalog; «no skill needed» counted separately; `rules_sure` marks weak rule advice.
- CI installs telethon; `tests/run_ci_local.sh` uses exactly the workflow's Python packages. `mila-export` test: fake secret literals glued at run time.

## v1.6.5 · 28.10 — the approved constitution, a clearer update plan, green tests everywhere
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- В конституции ядра закон 4 — в вашей утверждённой редакции, как у всех Мил.
- План обновления показывает пользу каждой новой версии короткой строкой — видно больше.

</details>

**For the owner**
- Law 4 of the core constitution is in your approved wording, as for every Mila.
- The update plan shows the benefit of each new version in a short line — you see more.

**For Milas**
- `CONSTITUTION.md`: law 4 = the owner-approved v2 text (20.09.2026), byte-equal to the fleet.
- `mila-update plan`: each «what you get» line ≤ 90 characters (`short_line`), lines of ≥ 3 versions fit in 900.
- Tests pass in any time zone: `test_spend_tap` uses real offsets, `effect._ts` parses UTC with `calendar.timegm`; `tests/run_ci_local.sh` runs the suite like GitHub (clean HOME, CI=true, UTC + a DST zone).

## v1.6.4 · 28.10 — the look-back sees your assignments, the constitution stays yours
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- «Оглядка» снова видит ваши поручения в переписке и находит забытые; служебные сообщения за ваши не принимает.
- План обновления больше не советует заменить конституцию: у вас может стоять ваша последняя редакция. Совет заменить старый сторож отправки остаётся.
- Проверка готовности перед событием принимает подтверждение только текстом.

</details>

**For the owner**
- The look-back sees your assignments in the chat again and finds forgotten ones; service messages are not taken for yours.
- The update plan no longer advises replacing the constitution: you may have your own latest wording. The advice to replace an old send guard stays.
- The readiness check before an event accepts a confirmation only as text.

**For Milas**
- `oglyadka`: the owner by the live channel tag (`user="<name>"`, not `user_id`): DM chat = owner, a group — by `--owner-user` / `OWNER_USERNAME`; non-numeric `message_id` (ticks, notes, file mail) is service inbound. In v1.6.3 it found 0 of 84 assignments on a live journal.
- `mila-update plan`: `recommend_take` only for the send guard; the constitution «differs» may be newer than the core.
- `bud-gotova`: proof must be a string.

## v1.6.3 · 28.10 — I come with a decision, get ready before events, keep the thread
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Прихожу к вам с решением, а не с вопросом: моё предложение, 2–3 варианта с последствиями и совет. Голый вопрос «когда? сколько?» не отправляю.
- Перед встречей, запуском или выступлением прохожу проверку по списку и закрываю, чего не хватает, до начала.
- Поток ваших поручений не теряю: каждое записываю, срочное беру сразу, почти готовое доделываю, днём и вечером перечитываю переписку — не забыла ли что.
- Жалобу на помощника сначала сверяю с его журналом и даю вам ответ фактами и готовый шаг.
- Перед показом деки или страницы — стилевой консилиум из трёх взглядов, чтобы выглядело профессионально.
- Трату выше порога, лимит и бюджеты меняю только по вашему нажатию кнопки.
- План обновления показывает главное из каждой новой версии и советует заменить устаревший сторож отправки.

</details>

**For the owner**
- I come to you with a decision, not a question: my proposal, 2–3 options with consequences and advice. I don't send a bare «when? how much?».
- Before a meeting, launch or talk I go through a checklist and close what is missing before the start.
- I don't lose the stream of your assignments: each is written down, urgent ones taken at once, nearly done ones finished; at midday and in the evening I reread the chat in case I forgot something.
- A complaint about an assistant is first checked against its journal; you get an answer with facts and a ready step.
- Before showing a deck or a page — a style council of three views so it looks professional.
- Spending above the threshold, limits and budgets change only when you press the button.
- The update plan shows the main point of each new version and advises replacing an outdated send guard.

**For Milas**
- New core skills (owner's word 28.10): `iniciativa` (`iniciativa_check.py`; `plain_words_check` runs it; `cards.py ask` needs `--rec` and a consequence per option), `bud-gotova` (`gotova.py`), `zhonglyor` (`zhonglyor.py`), `oglyadka` (`oglyadka.py` + `task.py scan-sent`), `stilnaya` (`stilnaya.py`), `razbor-lichki` (`razbor.py`).
- `spend` (SPEND-TAP): `approve <id> --card <card_id>` — the tapper comes from the plugin's `cards.jsonl`, not from `--by`; the same lock on `limit`, `budget`, `owner`. Until the receiver records which button was pressed, a spend card has one button «✅ Делаем».
- `mila-update plan`: «what you get» one line per version, x.y.0 first, trimmed after ordering; edits counted; send guard / constitution installed outside the update → «советую заменить», `recommend_take`, `apply --take`.
- README: the «nothing goes out without the owner's yes» row says what the code does.

## v1.6.2 · 28.10 — the update recognises its own files after a host rollout
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Обновление снова узнаёт свои файлы, если прошлое ставили с сервера: план показывает всё, что действительно обновится, а не малую часть.

</details>

**For the owner**
- The update recognises its own files again when the last one was installed from the server: the plan shows everything that will really change, not a small part.

**For Milas**
- `mila-update`: paths in `version.json` are re-based to the current home on load (`.claude/`, `work/`, `.local/`); before, a rollout from the host (MILA_HOME) stored host paths and every file looked «differs» — the v1.6.1 plan would update 6 skills instead of 36. `test_fleet_keys.sh`.
- `mila-update plan --json`: `get_versions` — which versions the «what you get» lines came from.

## v1.6.1 · 28.10 — the greeting in a client group, «switched on but not working»
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- В новой группе с вашим клиентом сначала здороваюсь коротко — стикер и «Привет, я …, искусственный интеллект.», потом приветствие клиенту, как у вас принято.
- Самопроверка теперь находит то, что включено, но не работает, — и подсказывает, что сделать.

</details>

**For the owner**
- In a new group with your client I first say a short hello — a sticker and «Hi, I'm …, an artificial intelligence.», then greet the client the way you do.
- The self-check now finds what is switched on but not working — and says what to do.

**For Milas**
- `mila-in-chat`: in a new client group — step 0 sticker and the one line, then the home's welcome canon (`canon/WELCOME-NEW-GROUP.md`) verbatim if present; other groups — only the sticker and the line (owner's word 28.10).
- `install/doctor.py`: `check_switches` — guest flow without MILAT_GUEST_CC=1 in the daemon's environment, missing guest key or prompt, review requests without handoffFile, student profile without prompt/folder, Jev without a gateway address, update cards without owner_chat.

## v1.6.0 · 28.10 — updates the owner can read, privacy at the source, the live screen, tasks without stalls
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Обновления теперь понятны: перед обновлением вижу и показываю вам план — что получите, что изменится, что не тронется, риск; обновляюсь только по вашей кнопке.
- Через несколько дней после обновления сама скажу, стало ли лучше; если хуже — предложу вернуть прежнюю версию одной кнопкой.
- Беру отзыв после каждой сданной работы, не теряю задачи и не называю часов сдачи — только «беру» и «вернусь с результатом».

</details>

**For the owner**
- Updates are now readable: before updating I see and show you a plan — what you get, what changes, what stays, the risk; I update only by your button.
- A few days after an update I tell you myself whether it got better; if worse, I offer to return the previous version with one button.
- I ask for feedback after every finished job, don't lose tasks and don't name delivery hours — only «I'm on it» and «I'll come back with the result».

**For Milas**
- `mila-update`: `plan` — readable update plan in the owner's card (all versions in between, changes by zone, untouched, risk; Russian owner blocks only); effect — «before» at apply, a «what changed» card 3–7 days later, judged by the share of answered messages, rollback only on the owner's press; `manual` — admin's manual inserts only with a journal record; `bootstrap-note` and the owner's yes for the first install on a client Mila.
- `skills/jev`: readiness for main only from a check against the truth (`jev.py check`), chat role / quoted author / to-other in the rules and the question, every decision logged (timeouts, main), `stats --hours`.
- `skills/screen` (new, core): the live screen at birth. `skills/raspisanie` (new): schedule that survives a session restart. `skills/obratnaya-svyaz` (new): feedback after every hand-over. `canon/BAZA-MILY.md`: ten base qualities.
- Tasks without stalls (ROLLOUT №41): receipt without delivery hours, a lost login no longer leaves a task hanging; `humanizer-ru` `proverka.py` — check outward Russian text (ROLLOUT №40).
- Subscription limit: probe after renewal instead of holding messages until «resets …»; send-guard checks photo and album captions.
- CI: tests independent of the clock (`test_limit_probe_clock`), job and apt step limits with retries.
- Privacy gate at the source (`tools/privacy_lint.py`, owner's root-cause review 25.10): a pre-commit hook refuses commits carrying our values (ids — also inside longer numbers, addresses, closed client slugs, names by stem); the closed list lives only outside the repo, CI reads it from an Actions secret and prints anonymous labels; `tests/fixtures/fake_people.py` — invented people and numbers for tests and examples. Tests and skill texts cleaned of real ids and client names.
- `mila-export` secret scanner (Mila Sila, Quality 🟢 25.10): 13 more kinds — sk_/rk_/pk_, AIza, fal uuid:hex, bot token without AA, Bearer, JWT, Slack xox, UPPERCASE env `*_KEY/TOKEN/SECRET/PASSWORD=` with a literal value, «пароль/parol:», long lines in overlapping chunks (a key after 20 000 characters is no longer missed); minified builds and `dist/` are scanned for explicit keys only; code expressions, placeholders and `*_FILE/_PATH/_DIR` names are not secrets. Live check: no new false findings on two Mila homes. Tests `test_scan` 18/18, `test_envkv` 7/7, `test_live` 25/25; `test_export` reads the manifest with Python `tarfile` (`tar --include` is BSD-only).
- `pd-vault` edges (Mila Sila, Quality 🟢 25.10): the key is checked and the vault saved before any file is changed (no more number lost when there is no key); local Uzbek phones («90 123 45 67», «(90) 123-45-67», a bare 9 digits after «тел/номер/звоните/whatsapp/aloqa uchun…») → one label per person (+998…); passports in any case and Cyrillic look-alikes; not masked: Telegram/chat ids, order/invoice numbers, amounts («на 1500000 сум»). `test_pd_kraya.py` 29/29, `test_pd_proby.py` 22/22.
- Stop hook `reply-required`: a message that arrives mid-turn (transcript record `attachment` / `queued_command`) is seen like any other — an owner question asked mid-turn and left unanswered now blocks. `test_reply_required.py` 22/22.
- `bot-send` edges (Mila Sila + Development + Quality, 25.10): one person once (111 and "111"), 429 — at most 3 retries ≤60 s, stop-list only when the person left (403/blocked/deactivated), no preview for 0 people or empty text, «/stop» unsubscribes; a bot-wide Telegram pause: ≤1 h by day — the rest waits and goes by itself, longer or into quiet hours — a new preview «N left — send after DD.MM HH:MM?», the owner's yes queues it; every deferred send (rest, night queue) has «Отменить» (`cancel`). `test_bot_send_kraya.py` 29/29.
- Stop hook `reply-required`: a flywheel tick, a file-mail note, a watcher signal (`watch-*`) and a senior's request answered by note don't demand a chat reply — only if every `<channel>` tag of the record is such; an owner question in the same record still blocks. `install/test_reply_required.py` 17/17 (first test of this hook).
- Old skill names (aliases in `legacy/skills/`) stay one more release: removing them needs a migration step that checks no cron still calls the old script paths — planned for v1.7.0.

## v1.5.3 · 25.10 — day board, plan-vs-fact, marketing checks, our secret scanner in CI
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Пульт дня: одно закреплённое сообщение — что в работе, что в очереди и что ждёт вашего ответа.
- Итог недели по пятницам одним постом-слайдами: план и факт.
- Проверка рекламы перед запуском: громкие слова без цифр и источника не пропускаю.

</details>

**For the owner**
- Day board: one pinned message — what is in progress, what is queued and what waits for your answer.
- Week results on Fridays as one slideshow post: plan and fact.
- Ad check before launch: loud words without a number or a source don't pass.

**For Milas**
- `skills/pult-dnya` (new): the day board — one pinned message for the owner (in progress / queue / waiting / done, each with a number, who, why, evidence, conclusion). A new task gets a «#N queued, after #X, because…» line at once; «waiting for you» exists only as a question with buttons asked that minute (`wait` refuses without `--asked`); at most two in progress, 🔴 always gets in; morning plan with a 3–5 task auto-pool, the board is edited during the day, evening results; closing needs evidence. `day_board.py` (cards, phones and e-mails masked; a wait over an hour turns 🔴), `test_pult.py` 22/22. Pinned board on demand: `render` returns «empty» and «waiting» for the plugin's `/status` with «#N — answer» buttons and never changes the day file; numbers that are not phones (request №, chat id, person id) stay. `test_pult.py` 26/26.
- `skills/plan-fakt` (new): Friday plan-vs-fact as one slideshow post — `collect.py` drafts the week from `WEEK.md`, day boards and `MONEY.md` (only if kept), personal data masked, an empty week says «нет данных»; `make_slides.py` 1080×1080 with any Chromium; `send_slideshow.py` one post. Test 17/17.
- Marketing set, first three skills: `ab-test`, `kreativ-proverka`, `metki-atribuciya` — rules only from primary sources with links (Meta A/B best practices, Telegram Ads guidelines, Hopkins). Superlatives without a number or source nearby — block, with one — warning; caps: one word — warning, two or more — block. `test_check_ad` 19/19.
- `bot-send`: the ✅ on the card covers the whole text in «…», the service compares by equality (a cut of an approved text no longer passes); broadcasts only when the fleet admin turns them on, a daily ceiling for one-to-one sends. 30/30.
- Send guard with `onFailure: block`: written by `install.sh` (new and existing entries) and added in place by `mila update` to installed send-guard hooks (backup, `migrate` journal, symlinks untouched) — only on Claude Code ≥ 2.1.295, older or unknown — skipped with a journal line. `test_install_hooks` 12/12.
- `jev --text -` reads the text from stdin, so group text is not in argv where `ps` shows it.
- Secrets: our own scanner (`mila_export scan`) runs over every tracked file in CI (`tests/test_secret_scan.py`, with planted fakes that must be caught); fake keys in tests and key/password patterns in code are built by splicing, so fleet snapshot scanners don't trip on the core; a password assignment is caught from 8 characters. `test_export` 40/40, `test_secret_scan` 10/10.

## v1.5.2 · 21.10 — English first, five questions about the model, fleet roll from the host
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Перед большой работой задаю 2–4 вопроса с готовыми вариантами — меньше переделок.
- Сложное и важное делаю сильной моделью, простое — лёгкой: дешевле без потери качества.
- Говорю на вашем языке, каким бы он ни был.

</details>

**For the owner**
- Before big work I ask 2–4 questions with ready options — fewer redos.
- Complex and important work goes to a strong model, simple work to a light one: cheaper without losing quality.
- I speak your language, whatever it is.

**For Milas**
- English first: `communication` and `onboarding` skills in English (`SKILL.md`) with Russian beside (`SKILL.ru.md`); the owner's language can be any (LANG-ANY): Chinese, Arabic…; on «what can you do» — one benefit, not a list.
- `skills/utochnenie-zadach` (new, base skill of every Mila): understand first, then do — 2–4 questions with ready options before substantial work; answers already given — no questions; urgent — result first with assumptions.
- `skills/model-choice`: five questions → model tier (`tier.py`: light | strong | strong+yes; a costly error always goes to the strong model; in someone's name or irreversible — strong model and the person's yes).
- `skills/draft-and-check` (new): a light model drafts, the strong model checks facts, numbers and tone against sources, the person's yes on that exact text sends it.
- `mila tasks` (`install/tasks.py`): task journal — kind, outcome (done / redo / complaint), cost from the turns of the task span; weekly report per task type.
- `skills/design-gates`: `fit_text.py` — does the text fit (wrap, largest size that fits, error with advice before writing files) for every visual skill.
- CI: DejaVu font installed; a test that skipped itself (`итог 0/0`) is ⚠ locally and fails in CI; tests run with stdin closed (`ffmpeg -nostdin`).
- README: Manifesto link (`milagpt.io/en/manifest/`), site links → `milagpt.io/en/mila/`, «One Mila, two wallets» — the subscription for the owner and work chats, customers and guests on OpenRouter tokens (guest routing in the hosted version today); compare table approvals row re-checked.
- `mila-update` fleet mode: `MILA_HOME` — update a Mila's home from the host; `MILA_CHOWN=uid[:gid]` — run as root, and only what this run wrote goes back to the home's owner (in-memory list, only inside the home: realpath + commonpath, no hard links). Rollback as root does not trust the journal or backups in the home (removal and unpacking only inside the home, no hard links or devices, symlinks only to targets inside). No access to the home → a clear error. `test_fleet.py` 11/11.
- `mila-update`: a Mila of the team itself (`"internal": true` in `mila-update.json`, or `MILA_INTERNAL=1` during a fleet roll) is not held by the newborn gate — she has no onboarding with an owner, so the core updates without `--newborn-ok`. Only the fleet admin sets it; every skip is written to the journal (`newborn_gate_skipped`, source config|env, apply|nightly) so a client Mila with the flag is visible. `test_update.sh` 26/26.

## v1.5.1 · 21.10 — safe, model choice, live frames, one-command install
<details><summary>In Russian (read by the updater of installed Milas)</summary>

**Для хозяина**
- Сейф: пароли и ключи вводите по одноразовой ссылке, не в чат.
- Перед платной работой (картинки, видео, голос) — два варианта с ценой, выбираете кнопкой.
- Видео-объяснение из голоса — без съёмки.

</details>

**For the owner**
- Safe: you type passwords and keys on a one-time link, not in the chat.
- Before paid work (images, video, voice) — two options with prices, you pick by button.
- An explainer video from voice — no filming.

**For Milas**
- One-command install: `curl -fsSL …/install/get.sh | bash` (checks Claude Code, Bun, git); CI runs `tests/run_all.sh` on every push; issue/PR templates, Code of Conduct.
- `skills/model-choice` (a partner's idea, 20.10): before any paid task (images, video, voice, transcription, translation, document analysis) Mila shows two options — budget / best quality: model, what you get, price for this job — with a recommendation, owner picks by button; `pick.py` + dated `catalog.json` (OpenRouter live, fal.ai, ElevenLabs). Test 6/6.
- Mila Safe (owner 20.10, «Да, делаем сейф»): `tools/seif` — one-time link (30 min, single use, GET does not burn it) where the business owner types passwords, keys and cards; values go straight to `work/secrets/<name>.env` (600) of the Mila's home, journal without values, note to the companion; `skills/safe-link` — never ask secrets in chat, request a safe link, read with `safe_read.py` (mask only). Tests 12/12, 6/6.
- `skills/live-frames` (new, from Mila Video, owner 20.10 «намного лучше»): explainer video from a voice track — moving background, Twemoji icons, counters, bars, arrows and pills appear on the spoken word, whoosh/pop/ticks and a ducked music bed, −14 LUFS; Pillow + numpy + ffmpeg, no paid graphics. Local word timing check (faster-whisper). Twemoji CC-BY 4.0, PT Sans OFL. Test: 3-second render with sound.
- `tools/hooks_sync.py` + template settings: mila-tasks hooks (PostToolUse reply → task-sent, SessionStart → task-open) for Milas deployed from the image (HOOKS-SYNC-1020).

## v1.5.0 · privacy and safety layer, 19.10
Personal data stays out of what Mila stores, card numbers never leave in a message, and a fresh self-hosted install comes with all its guards.

**For the owner**
- Card numbers are protected: a message with a bank card number (13–19 digits that pass the Luhn check) is never sent to a group, and in a private chat it goes out masked as ****1234. Your own payment details can be allowed in the config (`cardAllow` in access.json, `CARD_ALLOW` for bot sends).
- Personal data in Mila's memory is stored as labels, not as the data itself (pd-vault, encrypted on your machine).
- A fresh install already has every guard switched on: sending only to connected chats, no keys or internals in messages, tracking of what Mila promised you.
- New: a pack for clinics (booking and price list, with an exam).

**For Milas**
- `send-guard` (CARD-MASK): card number → deny to groups with the reason for the author, `updatedInput` with the mask in private chats; amount right after the number («… 1234 100 USD») does not hide it — the Luhn window is searched inside the digit chain, 16 digits first. `bot_send` masks in sends and broadcast previews.
- pd-vault (layer 2a): AES-256 + HMAC via openssl, labels instead of personal data; `pd-mask` PostToolUse hook; install creates the key by default.
- `install.sh` (SELFHOST): registers send-guard (PreToolUse reply/edit), task-sent and task-open (mila-tasks), `OWNER_ID` from `MILA_OWNER_ID`; send-guard falls back to access.json without OWNER_ID; installer copies every hook it registers.
- `skills/jev`: fast decider — reply / who / buttons, modes off | shadow | main, 1.2 s timeout → rules, diff log without texts.
- `mila-update`: `install-skill` refuses an incomplete skill (files named in SKILL.md missing → list, `--allow-missing` to install knowingly); `remove-skill` with backup, core skills protected.
- `packs/clinic` v0.1: clinic-booking, clinic-prices, exam (Sila's patient scenarios ×3), no condition names (diagnosis), data in `~/work/clinic/`.
- README: release badge and «which version to take» (stable — Releases, canary — main); REFERENCE licence fixed to Apache-2.0.
- Tests: `tests/run_all.sh` — ALL GREEN 17.

## v1.4.0-rc4 · fix (candidate)
- 🔴 `install.sh` (since rc3) registered `reply-required.py` as a Stop hook but did not copy the file: on a fresh install every stop failed with exit code 2, which means «don't stop» — the session would loop. Now every hook the installer registers is copied; `install/test_install_hooks.sh` checks that each hook in settings.json exists as a file. Updates via mila-update were not affected (install/*.py are copied by the release zones; settings.json is not touched).

## v1.4.0-rc3 · code improvements (candidate)
- `tests/run_all.sh`: every test in the repo + frontmatter in one command (11, ~9 s), exit code 1 on any failure; in release.sh and CONTRIBUTING.
- `install.sh` registers `reply-required.py` as a Stop hook (promised by README/REFERENCE, was manual); `--dry-run` lists every hook; owner's own hooks and settings kept, backup made, re-run does not duplicate.
- `mila` on Linux: daemons via `systemctl --user` (units from deploy/bootstrap.sh), macOS keeps launchctl; per-OS hints.
- `docs/exam-example/`: example guest prompt + exam yaml + README for `tools/express_exam.mjs`; fix: planted failures with ids like `s01` were not matched.

## v1.4.0-rc2 · bilingual skill descriptions (candidate)
- 46 skills: `description` = English first (what + when + English triggers), then `RU:` with the original Russian — English-speaking owners' models find the skills, Russian triggers keep working. `mila-session` was already English.

## v1.4.0-rc1 · international names (candidate)
Skills get English names; old names keep working until v1.6.0. Owner 17.10 (33645).

**For the owner**
- Skills now have international names (cards, plain-words, onboarding…) — your Mila finds and updates them the same way.
- Nothing you changed is lost: if you edited a renamed skill, your version is kept next to the new one.
- Old commands and paths keep working for two more versions.

**For Milas**
- Renamed: ekzamen→exam · kartochki→cards · lichka-hozyaina→owner-dm · mila-v-chate→mila-in-chat · naglyadno→visual · proverka→verify · put-gostya→guest-path · rashod→spend · topiki→topics · vhodyashchie→inbox · vkusy→tastes · voprosy→questions · yasno→plain-words · zadachi→tasks · znakomstvo→onboarding; canon/OBDUMYVANIE→THINKING-BUDGET; docs/uchet→docs/accounting. Scripts: cards.py, plain_words_check.py, spend.py.
- Old names are aliases: `MOVED.md` + script wrappers (old paths exec the new scripts), no SKILL.md — not loaded as skills, no duplicates.
- `mila-update`: `renamed` in release.json — the old folder becomes the alias even if the owner edited it; the edit is saved to `mila-update/new/<tag>/было-<old>` and reported (`pereimenovano`, `pravka_starogo_imeni`). Test `test_renamed.sh` 10/10, in release.sh.
- Data paths are not renamed (`~/work/rashod`, `.kartochki-shown.json`, `memory/vkusy.md`, `work/topiki/`) — owners keep their history.

## v1.3.0 · lessons of Mila Tashkent, 17.10
What a working sales Mila learned in one day (exam "Guest path" 15/15), now in the core for every Mila.

**For the owner**
- Your Mila answers guests in their language and offers a trial no later than her third answer.
- In your private chat: your question first, attachments opened, one summary instead of three, no technical noise.
- Exams in minutes: after every change your Mila's sales script is checked in under a minute, the live check runs at night.

**For Milas**
- `put-gostya` (new): the guest path — guest's language (ru/uz/en, no forced translation), benefit + trial offer by the 3rd answer, invoice as a card ("choose a way on the card; transfer — screenshot here"; Stars/USDT for foreigners), soft no + legal path for illegal requests, "what to send" — one-line example, follow the link label's path.
- `lichka-hozyaina` (new): seven rules for the owner's DM — owner's question before the feed, open attachments, no "Send?" without a draft, don't relay reactions, no file paths or internals, 2–3 buttons, one summary.
- `ekzamen` (new) + `tools/express_exam.mjs`: one yaml for the express run (subscription, minutes, --repeat, planted failures, prompt sha) and the nightly live run; full guest reset before each scenario.
- `canon/OBDUMYVANIE.md`: reasoning models need max_tokens headroom (empty answers at 220 tokens).
- `vkusy` (new, since v1.2.0 on main): the owner's tastes — remember, ask once, three picks with "why you"; a voice speaker of a connected owner hands requests to his Mila.
- README.ru: same positioning as the English README.
- Links: client-chat and lead-qualify → put-gostya; communication → lichka-hozyaina.

## v1.2.0 · Mila Companion 1.0 — first public release
An open-source digital employee for your business, living in Telegram. The README now says what Mila is and how she compares with universal agents.

**For the owner**
- Before saying "done", your Mila checks the result against its "done if" and shows the proof.
- A newborn Mila starts from what you already told at the consultation, not from a questionnaire.
- The same remark three times becomes a rule — she asks you before writing it down.

**For Milas**
- `proverka` (new): check a result against its "done if" — YES / NO / CAN'T CHECK with a verbatim quote, last line DONE / HOLD; action items need evidence from a tool output.
- `crm-dialogs`: what I know about a person carries a source label (said himself / my conclusion / not said); labels live only in cards and notes, never in text to a person.
- `self-check`: owner's remarks go to `memory/zamechaniya.md`; the third identical remark → an exact line for SKILL.md and "Add it?".
- `znakomstvo`: step 0a — the first message comes from the guest card; "which task first" — 2–3 options and three questions about the past (how often, minutes, sign of "done").
- README: positioning (digital employee, Telegram-native), comparison with OpenClaw / NanoClaw / Hermes Agent with sources, who builds Mila, invitation to developers.

## v1.1.0 · open release
The core is now open source (Apache-2.0) and updates itself from git.

**For the owner**
- Your Mila checks for new versions every night and tells you what is new in three lines.
- Updates never touch your files, memory, settings or keys; any update can be undone.
- You choose: ask me first (default) or let her update by herself.
- Your Mila belongs to you: `mila export` packs her into one archive (no keys), `mila restore` brings her back on any machine.

**For Milas**
- `mila-export` — `mila export` / `mila restore`: the whole Mila (instructions, skills, memory, crons, settings, plugin list) in one `tar.gz` with `manifest.json` (format 1, sha256) and `RESTORE.md`; built-in secret scanner, the export fails on a hit; restore verifies, never overwrites, prints a re-enter checklist. `release.json` gets `genes` (every Mila carries mila-export and mila-update).
- `mila-update`: channels `stable` (tags `vX.Y.Z`) and `canary` (`main`); settings in `~/.claude/mila-update.json` (`channel`, `auto`, `repo`, `owner_chat`, `require_signed`).
- `update.py nightly [--dry-run]`: fetch tags, skip yanked and `-rc`, dry run (manifest, skill frontmatter, hook syntax), crons copy, apply, health check, automatic rollback on failure, journal, owner card from this CHANGELOG.
- `yanked.json` in the repo withdraws a release; a withdrawn version is never installed.
- Never touched: `state/`, `.credentials.json`, `.claude.json`, `mila-update.json` (added to the built-in list).
- Tests run on macOS (no GNU sed, no pyyaml needed); `tools/release.sh` is the release procedure (see CONTRIBUTING).

## v1.0 · first release
Mila Companion — a personal AI companion in Telegram that runs on the owner's Claude subscription.

**Highlights**
- `bot-send` — messages and mailings through the owner's public bot: the companion files a request, a host-side gate holds the bot token; only people who wrote to the bot; preview → owner's ✅; rate limit, stop list, quiet hours.
- `send-guard` hook with `"onFailure": "block"` (Claude Code 2.1.295+): if the guard fails or hangs, the message is not sent at all rather than sent unchecked.
- `packs/webmaster` (optional): site development and production deploys by the companion itself.
- `yasno` — the language of owner-facing cards: clear on first read, 9 rules in the spirit of ASD-STE100, a glossary, `yasno_check.py`.
- `mila-update` — the companion knows her core version, compares it with the release, updates only after the owner's yes, with backup and rollback. `release.json` lists what is updated and what never is.

**Core skills:** bot-send · client-chat · communication · copyblock · crm-dialogs · design-gates · dialog-close · escalate-to-owner · flashcards · humanizer-ru · inbox-triage · infographic · mail-outbound · mila-session · mila-tasks · mila-update · mila-v-chate · mini-podcast · naglyadno · polite-no · rashod · reply-from-examples · subscription · subscription-limits · topiki · video-overview · vhodyashchie · voprosy · yasno · youtube-research · zadachi · znakomstvo · kartochki · tasks-discipline · inbox-triage.

**Hooks and tools:** telegram-inbox-feed, reply-required, transcribe-voice, usage/turns collect, records, chats_index, chat_note, chat_locale, doctor, backup, design_check, limit_watch, companion-feeder; the `mila` launcher.

**Canon** (`canon/`): LIVE-TODAY, REFRAME, WEEK-RHYTHM; TEAM-CONTACTS is a template (`.example`), every team keeps its own.

**Constitution** v2.1 — one for all Milas.
