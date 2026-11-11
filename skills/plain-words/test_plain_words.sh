#!/usr/bin/env bash
# пробы plain_words_check.py (проверка): запретные слова — целым словом с формами, не подстрокой;
# вопрос без предложения и рекомендации — замечание (проверка iniciativa_check рядом)
H="$(cd "$(dirname "$0")" && pwd)"; ok=0; n=0
pass() { n=$((n+1)); if python3 "$H/plain_words_check.py" "$1" >/dev/null; then ok=$((ok+1)); echo "✅ ясно: $1"; else echo "❌ ждали «ясно»: $1"; fi; }
fail() { n=$((n+1)); if ! python3 "$H/plain_words_check.py" "$1" >/dev/null; then ok=$((ok+1)); echo "✅ поймано: $1"; else echo "❌ ждали замечание: $1"; fi; }
pass "Продлить подписку?
⭐ Советую: продлить — сайт работает дальше"
pass "Предлагаю новый продукт к лету — спрос растёт.
Если не против, начну план сегодня."
fail "Выложить квиз на прод?"
fail "Сколько лидов пришло?"
pass "Квиз зала: показать на экране сегодня?
⭐ Советую: показать — зал ждёт"
fail "Продлить подписку?"
fail "Сколько роликов сделать на неделю?"
fail "Выложить квиз на прод сегодня? Решай сама"
# --- края: пустое, латиница и кальки. У каждой карточки ниже есть строка совета — чтобы замечание
# давало только проверяемое слово, а не «вопрос без предложения» (проверка инициативы рядом)
fail ""
fail "   "
n=$((n+1)); if printf '' | python3 "$H/plain_words_check.py" 2>&1 | grep -q "проверять нечего"; then ok=$((ok+1)); echo "✅ пустой stdin: проверять нечего"; else echo "❌ пустой stdin"; fi
for w in deploy prod preview lead leads deadline onboarding dashboard push merge commit bundle CI; do fail "Нужно: $w сегодня?
⭐ Советую: да — так проще"; done
fail "Сделать Deploy сегодня?
⭐ Советую: да — так проще"
pass "Нужен ли leader в команде?
⭐ Советую: да — так проще"
pass "Новый product готов?
⭐ Советую: да — так проще"
pass "Подробности в ci-файле?
⭐ Советую: да — так проще"
n=$((n+1)); if python3 "$H/plain_words_check.py" "Выложить на prod?
⭐ Советую: да — так проще" | grep -q "на сайте"; then ok=$((ok+1)); echo "✅ замена из словаря в замечании"; else echo "❌ замена не названа"; fi
# --- кальки кириллицей, точные английские формы, main
for w in "пуш в main" "коммит готов" "нужен мерж" "собрали бандл" "сделали пуши" "после мержа"; do fail "Готово: $w?
⭐ Советую: да — так проще"; done
for w in commits committed merged pushed deployed bundles previews deadlines dashboards leads; do fail "Нужно: $w сегодня?
⭐ Советую: да — так проще"; done
pass "Это Commitment команды?
⭐ Советую: да — так проще"
pass "Нужен ли Pushkin в списке?
⭐ Советую: да — так проще"
pass "Что такое maintenance окно?
⭐ Советую: да — так проще"
pass "Подробнее на главной странице?
⭐ Советую: да — так проще"
n=$((n+1)); if python3 "$H/plain_words_check.py" "Готово: пуш в main" | grep -q "основная версия"; then ok=$((ok+1)); echo "✅ main → основная версия"; else echo "❌ main"; fi
# a replacement the checker suggests must itself pass the checker: no hint may point to a word from the banned list
n=$((n+1)); if python3 - "$H" <<'PYEOF'
import re, sys
sys.path.insert(0, sys.argv[1]); import plain_words_check as P
bad = [ru for ru in P.HINTS.values() if any(re.search(r"(?<!\w)(?:" + w + r")(?!\w)", ru, re.I) for w in list(P.BANNED) + list(P.HINTS))]
sys.exit(1 if bad else 0)
PYEOF
then ok=$((ok+1)); echo "✅ ни одна замена сама не из запретных слов"; else echo "❌ замена из запретных слов"; fi
echo "итог $ok/$n"; [ $ok = $n ]
