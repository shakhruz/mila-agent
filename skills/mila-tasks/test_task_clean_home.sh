#!/usr/bin/env bash
# task.py в чистом доме: SessionStart-хук, новое дело, закрытие с уликой, список — без NameError (пути задачника на месте).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME/work"; unset MILA_TASKS_DIR MILA_NOW_MD TELEGRAM_STATE_DIR
P="python3 $HERE/task.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
chk "хук SessionStart в чистом доме — без ошибки" "python3 $HERE/hooks/task-open.py </dev/null 2>$T/e; ! grep -q Error $T/e"
chk "open --short в чистом доме — код 0" "$P open --short >/dev/null 2>$T/e2"
$P new --title "проверить пак" --check "pack-plan отвечает" >$T/o3 2>$T/e3
chk "новое дело — в ledger.jsonl под ~/work/tasks, без NameError" "[ -s $HOME/work/tasks/ledger.jsonl ] && ! grep -q Error $T/e3"
chk "дело видно в open" "$P open 2>/dev/null | grep -q 'проверить пак'"
echo "итог $ok/$n"; [ $ok -eq $n ]
