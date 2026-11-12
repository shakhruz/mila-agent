#!/bin/bash
# get.sh: из локальной копии репо в пустой HOME — клонирует, ставит (install.sh), повторный запуск обновляет; без git — честная
# подсказка и выход 1. Без сети. bash install/test_get.sh
export MILA_SKIP_TIMERS=1   # the installer writes its timers and never loads them here: a test must not start a job on the machine that runs it
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'chmod -R u+w "$T" "${T3:-}" "${T4:-}" "${T5:-}" 2>/dev/null; rm -rf "$T" "${T3:-}" "${T4:-}" "${T5:-}"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
# Источник — копия репо с веткой на текущем коммите: так тест работает и в detached HEAD (CI, проверка Качества),
# где rev-parse --abbrev-ref даёт «HEAD» и git clone --branch HEAD падает.
SRC=$T/src; git clone -q "$H" "$SRC"; git -C "$SRC" checkout -q -B mila-test "$(git -C "$H" rev-parse HEAD)"; B=mila-test
run(){ HOME=$T MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh"; }   # без MILA_DIR — папка по умолчанию
run > $T/o1.txt 2>&1
chk "клон в ~/mila (по умолчанию) и установка навыков в ~/.claude/skills" "[ -d $T/mila/.git ] && [ -d $T/.claude/skills ] && ls $T/.claude/skills | grep -q mila-update"
chk "в конце — шаги «дальше» и mila doctor" "grep -q 'mila doctor' $T/o1.txt"
run > $T/o2.txt 2>&1
chk "повторный запуск — обновление, не ошибка" "grep -q 'updating' $T/.claude/mila-install.log"
chk "без git — подсказка и выход 1" "! env -i HOME=$T PATH=/nonexistent /bin/bash $H/install/get.sh > $T/o3.txt 2>&1 && grep -q 'git' $T/o3.txt"
R2=$T/rel2; git clone -q "$H" $R2; git -C $R2 tag v9.9.9 >/dev/null 2>&1; git -C $R2 tag v10.0.0-rc1 >/dev/null 2>&1
HOME=$T MILA_SKIP_CHECKS=1 MILA_REPO="$R2" MILA_DIR="$T/m2" bash "$H/install/get.sh" > $T/o4.txt 2>&1
chk "без MILA_REF — последний стабильный тег (v9.9.9, не rc)" "grep -q 'version: v9.9.9' $T/.claude/mila-install.log && [ -d $T/m2/.git ]"
T3=$(mktemp -d); git clone -q "$SRC" "$T3/mila-companion"   # старая установка до переименования
HOME=$T3 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o5.txt 2>&1
chk "старая ~/mila-companion обновляется на месте, вторую папку ~/mila не заводит" "grep -q 'updating $T3/mila-companion' $T3/.claude/mila-install.log && [ ! -d $T3/mila ]"; rm -rf $T3
T4=$(mktemp -d); mkdir -p "$T4/mila"; git -C "$T4/mila" init -q; echo x > "$T4/mila/notes.txt"; git -C "$T4/mila" add -A; git -C "$T4/mila" -c user.email=a@b -c user.name=a commit -qm x
HOME=$T4 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o6.txt 2>&1; rc=$?
chk "~/mila — чужой git-проект: честный отказ, выход 1, проект не тронут" "[ $rc -eq 1 ] && grep -q 'already used' $T/o6.txt && [ -f $T4/mila/notes.txt ] && [ ! -d $T4/mila/skills ] && [ \$(git -C $T4/mila log --oneline | wc -l) -eq 1 ]"; rm -rf $T4
# плагин Telegram тем же запуском: заглушка claude пишет свои вызовы
T5=$(mktemp -d); mkdir -p $T5/bin; printf '#!/bin/sh\necho "$@" >> %s/calls\n' "$T5" > $T5/bin/claude; chmod +x $T5/bin/claude
HOME=$T5 PATH="$T5/bin:$PATH" MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o7.txt 2>&1
chk "плагин: marketplace add shakhruz/mila-telegram, затем install mila-telegram@mila" "grep -qx 'plugin marketplace add shakhruz/mila-telegram' $T5/calls && grep -q '^plugin install mila-telegram@mila' $T5/calls && grep -q '✓ Telegram' $T/o7.txt"
rm -f $T5/calls; HOME=$T5 PATH="$T5/bin:$PATH" MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" MILA_INSTALL_ARGS=--dry-run bash "$H/install/get.sh" > $T/o8.txt 2>&1
chk "--dry-run: плагин не ставится, только «would run»" "[ ! -e $T5/calls ] && grep -q 'would run' $T/o8.txt"; rm -rf $T5
# get.sh выпуска: вшитые тег и SHA его коммита (как штампует tools/release.sh); тег сдвинули — не ставит
pin(){ sed -e "s/^PIN_REF=\"\"$/PIN_REF=\"$B\"/" -e "s/^PIN_SHA=\"\"$/PIN_SHA=\"$1\"/" "$H/install/get.sh" > $T/get-pin.sh; }
GOOD=$(git -C "$SRC" rev-parse HEAD); pin "$GOOD"
HOME=$T MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_DIR="$T/p1" bash $T/get-pin.sh > $T/o9.txt 2>&1; rc=$?
chk "get.sh выпуска: свой тег, SHA совпал — ставит и печатает коммит" "[ $rc -eq 0 ] && grep -q 'this get.sh was released for it' $T/.claude/mila-install.log && grep -q \"commit: $GOOD\" $T/.claude/mila-install.log"
pin deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
HOME=$T MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_DIR="$T/p2" bash $T/get-pin.sh > $T/o10.txt 2>&1; rc=$?
chk "get.sh выпуска: тег указывает на другой коммит — отказ, выход 1, install.sh не запускался" "[ $rc -eq 1 ] && grep -q 'nothing installed' $T/o10.txt && ! grep -q 'mila doctor' $T/o10.txt"
chk "в репо PIN_REF и PIN_SHA пустые (штамп — только у файла выпуска)" "grep -qx 'PIN_REF=\"\"' $H/install/get.sh && grep -qx 'PIN_SHA=\"\"' $H/install/get.sh"
# вывод для новичка: предупреждение git о метке не показывается, настоящая ошибка git — показывается; подсказка о плагине не идёт раньше плагина
chk "через get.sh подсказки «No Telegram plugin yet?» нет — плагин ставится тем же запуском" "! grep -q 'No Telegram plugin yet' $T/o1.txt && ! grep -q 'No Telegram plugin yet' $T/o7.txt && ! grep -q 'No Telegram plugin yet' $T/o11.txt"
HOME=$T/solo CLAUDE_CONFIG_DIR=$T/solo/.claude bash "$H/install/install.sh" > $T/o11.txt 2>&1
chk "install.sh сам по себе говорит прямо, что плагин Telegram ещё не поставлен, и как" "grep -q 'Telegram .*not installed yet' $T/o11.txt && grep -q 'plugin install mila-telegram@mila' $T/o11.txt"
chk "через get.sh строки «not installed yet» нет — плагин уже поставлен (или пропущен словом)" "! grep -q 'not installed yet' $T/o7.txt && grep -q 'Telegram .*skipped' $T/o1.txt"
chk "сказано прямо: хуки работают в каждой сессии Claude Code этого пользователя" "grep -q 'run in EVERY Claude Code session of this user' $T/o1.txt && grep -q 'run in EVERY Claude Code session of this user' $T/o11.txt"
T6=$(mktemp -d); mkdir -p $T6/bin; REALGIT="$(command -v git)"
printf '#!/bin/sh\ncase " $* " in *" clone "*) echo "warning: refs/tags/v9.9.9 0123abc is not a commit!" >&2;; esac\nexec %s "$@"\n' "$REALGIT" > $T6/bin/git; chmod +x $T6/bin/git
HOME=$T6 PATH="$T6/bin:$PATH" MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o12.txt 2>&1; rc=$?
chk "git предупредил «is not a commit!» при клонировании по метке — в выводе установки этой строки нет, установка прошла" "[ $rc -eq 0 ] && ! grep -q 'is not a commit' $T/o12.txt && grep -q 'mila doctor' $T/o12.txt"
T7=$(mktemp -d)
HOME=$T7 MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$T/net-takogo-repo" MILA_REF="$B" bash "$H/install/get.sh" > $T/o13.txt 2>&1; rc=$?
chk "настоящая ошибка git (репозитория нет) — видна, выход не 0, установка не начиналась" "[ $rc -ne 0 ] && grep -qi 'fatal\|not .*repository\|does not exist' $T/o13.txt && ! grep -q 'mila doctor' $T/o13.txt"
git -C $T6/mila remote set-url origin "$T/net-takogo-repo"
HOME=$T6 MILA_INSTALL_VERBOSE=1 MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o14.txt 2>&1; rc=$?
chk "обновление не скачалось (источник пропал) — выход не 0, ошибка видна, прежняя версия молча заново не ставится" "[ $rc -ne 0 ] && grep -q 'updating' $T/o14.txt && grep -q 'could not download' $T/o14.txt && ! grep -q 'commit:' $T/o14.txt && ! grep -q 'mila doctor' $T/o14.txt"
rm -rf $T6 $T7
# ── the screen of a normal run: short, English, true counts; the details are in the log (mode 600); --verbose shows them
nocyr() { python3 -c "import re,sys; sys.exit(1 if any(re.search('[\u0400-\u04ff]', l) for l in open(sys.argv[1], encoding='utf-8') if 'hello' not in l) else 0)" "$1"; }
LOGF=$T/.claude/mila-install.log
NSK=$(ls -d $H/skills/*/ | wc -l | tr -d ' ')
chk "экран обычной установки — только английский (кириллица лишь в строке приветствия): первая установка, повтор и install.sh сам по себе" "nocyr $T/o1.txt && nocyr $T/o2.txt && nocyr $T/o11.txt && grep -q 'hello · привет · salom' $T/o1.txt"
chk "экран короткий (до 30 строк), построчного перечня навыков и хуков на нём нет" "[ \$(wc -l < $T/o2.txt) -le 30 ] && ! grep -q 'unchanged, no copy needed' $T/o2.txt && ! grep -q 'hook →' $T/o2.txt"
chk "число навыков на экране = числу навыков набора = числу навыков, лежащих в доме" "grep -q \"✓ $NSK skills\" $T/o2.txt && [ \$(ls -d $T/.claude/skills/*/ | wc -l | tr -d ' ') -eq $NSK ]"
NHK=0; for f in telegram-inbox-feed crons-keeper reply-required pd-mask send-guard done-guard secret-guard skill-hint hod-stream; do [ -x $T/.claude/hooks/$f.py ] && NHK=$((NHK+1)); done
chk "число стражей на экране = числу установленных файлов хуков (9)" "[ $NHK -eq 9 ] && grep -q '✓ $NHK guardians' $T/o2.txt"
chk "журнал установки: есть, права 600, в нём построчные факты (навыки, хуки, инструменты) и шаги get.sh" "python3 -c \"import os,sys; sys.exit(0 if os.stat(sys.argv[1]).st_mode & 0o777 == 0o600 else 1)\" $LOGF && grep -q 'unchanged, no copy needed' $LOGF && grep -q 'hook → ' $LOGF && grep -q 'doctor.py' $LOGF && grep -q 'commit: ' $LOGF"
chk "последняя инструкция — один шаг mila; ни «Next / дальше», ни onboard-списка" "grep -q 'One step left' $T/o2.txt && grep -q '^      [^ ]*mila$' $T/o2.txt && grep -q 'mila doctor' $T/o2.txt && ! grep -q 'Next / ' $T/o2.txt && ! grep -q 'BotFather' $T/o2.txt"
T8=$(mktemp -d)
HOME=$T8 MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" --verbose > $T/o15.txt 2>&1
chk "--verbose: построчные факты — и на экране тоже" "grep -q 'unchanged, no copy needed\|installed' $T/o15.txt && grep -q 'hook → ' $T/o15.txt && grep -q 'updating\|cloning into' $T/o15.txt"
rm -rf $T8; T8=$(mktemp -d)
HOME=$T8 MILA_INSTALL_VERBOSE=1 MILA_SKIP_PLUGIN=1 MILA_SKIP_CHECKS=1 MILA_REPO="$SRC" MILA_REF="$B" bash "$H/install/get.sh" > $T/o16.txt 2>&1
chk "MILA_INSTALL_VERBOSE=1 — то же, что --verbose" "grep -q 'hook → ' $T/o16.txt"
rm -rf $T8
chk "ANSI-цвета в выводе не пишутся (не терминал)" "! grep -q \$'\\033' $T/o2.txt"
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
