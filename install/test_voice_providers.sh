#!/bin/bash
# Голос: Deepgram первым (nova-3, multi), Groq вторым; ключи из env или сейфа; уверенный Deepgram — его текст; неуверенный
# (узбекский у Deepgram нет) — Groq, если его ключ есть, иначе текст Deepgram. Сеть подменена: поддельный curl.
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1  ← $(eval "$3" 2>&1 | head -c 200)"; fi; }
mkdir -p "$T/bin" "$T/sec"
cat > "$T/bin/curl" <<'C'
#!/bin/bash
printf '%s\n' "$*" >> "$CURL_LOG.argv"   # what other processes would see in ps
for a in "$@"; do case "$a" in Authorization:*) printf '%s\n' "$a" >> "$CURL_LOG";; @-) grep '^Authorization:' >> "$CURL_LOG";; http*) printf 'URL %s\n' "$a" >> "$CURL_LOG";; esac; done
case "$*" in   # NET_DOWN names a service that cannot be reached: the real curl prints only its -w line («000») and exits 7
  *listen*) case "${NET_DOWN:-}" in *deepgram*) case "$*" in *http_code*) printf '\n000';; esac; exit 7;; esac;;
  *transcriptions*) case "${NET_DOWN:-}" in *groq*) exit 7;; esac;;
esac
case "$*" in
  */status*) echo "${KEYD_STATUS:-}";;
  *listen*) if [ "${DG_CODE:-200}" = 200 ]; then echo "{\"results\":{\"channels\":[{\"alternatives\":[{\"transcript\":\"$DG_SAYS\",\"confidence\":$DG_CONF}]}]}}"; else echo '{"err_code":"INVALID_AUTH"}'; fi
            case "$*" in *http_code*) echo "${DG_CODE:-200}";; esac;;
  *transcriptions*) echo '{"language":"uzbek","text":"salom dunyo"}';;
esac
C
chmod +x "$T/bin/curl"; export PATH="$T/bin:$PATH" SAFE_DIR="$T/sec" CURL_LOG="$T/auth.log" HOME="$T"
DK="dg""_file""$RANDOM""xyz"; GK="gsk""_file""$RANDOM""abc"; umask 077; : > "$T/a.ogg"
run() { env -u GROQ_API_KEY -u DEEPGRAM_API_KEY "$@" bash "$H/install/transcribe-voice.sh" "$T/a.ogg" 2>&1; }
printf "DEEPGRAM_API_KEY='%s'\n" "$DK" > "$T/sec/deepgram.env"
o=$(DG_SAYS="привет мир" DG_CONF=0.93 run); chk "только Deepgram, уверен — его текст" '[ "$o" = "привет мир" ]' 'echo "$o"'
chk "…ключ Deepgram — заголовком Token, из сейфа" 'grep -q "Authorization: Token $DK" "$T/auth.log"' 'cat "$T/auth.log"'
o=$(DG_SAYS="salom" DG_CONF=0.31 run); chk "только Deepgram, не уверен (узбекский) — всё равно его текст, Groq не зовём" '[ "$o" = "salom" ] && ! grep -q Bearer "$T/auth.log"' 'echo "$o"'
printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"; : > "$T/auth.log"
o=$(DG_SAYS="salom" DG_CONF=0.31 run); chk "Deepgram не уверен и есть Groq — текст Groq (uz)" '[ "$o" = "salom dunyo" ] && grep -q "Bearer $GK" "$T/auth.log"' 'echo "$o"'
: > "$T/auth.log"; o=$(DG_SAYS="привет мир" DG_CONF=0.93 run); chk "Deepgram уверен — Groq не зовём, даже если его ключ есть" '[ "$o" = "привет мир" ] && ! grep -q Bearer "$T/auth.log"' 'echo "$o"'
rm "$T/sec/groq.env"
o=$(DG_CODE=401 run); rc=$?; chk "Deepgram 401 (неверный ключ), Groq нет — код ≠ 0 (приёмник скажет «не расшифровано»), причина в журнал" 'echo "$o" | grep -q "ключ не принят (HTTP 401)" && ! echo "$o" | grep -q "$DK"' 'echo "$o"'
chk "ключи Deepgram и Groq — не в аргументах curl (их видит ps), а заголовком из stdin" '! grep -q -e "$DK" -e "$GK" "$T/auth.log.argv" && grep -q -- "-H @-" "$T/auth.log.argv"' 'cat "$T/auth.log.argv"'
o=$(DG_CODE=402 run); chk "Deepgram 402 — «кончился кредит»" 'echo "$o" | grep -q "кончился кредит"' 'echo "$o"'
o=$(DG_CODE=429 run); chk "Deepgram 429 — «лимит запросов»" 'echo "$o" | grep -q "лимит запросов"' 'echo "$o"'
printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"
o=$(DG_CODE=401 run); chk "Deepgram 401, есть Groq — ответ Groq" 'echo "$o" | tail -1 | grep -q "salom dunyo"' 'echo "$o"'
rm "$T/sec/deepgram.env"; o=$(run); chk "только Groq (как во флоте) — путь прежний" '[ "$o" = "salom dunyo" ]' 'echo "$o"'
rm "$T/sec/groq.env"; o=$(run); chk "ни одного ключа — понятная строка и код 1" 'echo "$o" | grep -q "нет ключа распознавания"' 'echo "$o"'
o=$(DEEPGRAM_API_KEY="dg_env_1" DG_SAYS="ok" DG_CONF=0.9 bash "$H/install/transcribe-voice.sh" "$T/a.ogg" 2>&1); chk "ключ Deepgram из env" '[ "$o" = "ok" ]' 'echo "$o"'
# the key keeper (Mila Agent): no key in the script — the request goes to the keeper with a placeholder
: > "$T/auth.log"; o=$(MILA_KEYD=http://keyd KEYD_STATUS='{"anthropic": true, "deepgram": true, "groq": true}' DG_SAYS="через хранителя" DG_CONF=0.9 run)
chk "хранитель ключей: Deepgram через него (/deepgram/v1/listen), в заголовке заглушка, не ключ" '[ "$o" = "через хранителя" ] && grep -q "URL http://keyd/deepgram/v1/listen" "$T/auth.log" && grep -q "Authorization: Token mila-keyd" "$T/auth.log"' 'cat "$T/auth.log"'
: > "$T/auth.log"; o=$(MILA_KEYD=http://keyd KEYD_STATUS='{"anthropic": true, "deepgram": false, "groq": true}' run)
chk "хранитель: только Groq — через него (/groq/openai/…), заглушка" '[ "$o" = "salom dunyo" ] && grep -q "URL http://keyd/groq/openai/v1/audio/transcriptions" "$T/auth.log" && grep -q "Bearer mila-keyd" "$T/auth.log"' 'cat "$T/auth.log"'
o=$(MILA_KEYD=http://keyd KEYD_STATUS='{"anthropic": true, "deepgram": false, "groq": false}' run); chk "хранитель без ключей голоса — «нет ключа», код 1" 'echo "$o" | grep -q "нет ключа распознавания"' 'echo "$o"'
# --- a service that cannot be reached over the network: a reason in the log, never a silent exit with curl's code
printf "DEEPGRAM_API_KEY='%s'\n" "$DK" > "$T/sec/deepgram.env"; printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"
o=$(NET_DOWN=deepgram run); rc=$?; chk "Deepgram недоступен по сети, Groq есть — причина в журнале и текст Groq, код 0" '[ $rc = 0 ] && echo "$o" | grep -q "Deepgram: сервис не ответил" && echo "$o" | grep -q "salom dunyo"' 'echo "rc=$rc $o"'
o=$(NET_DOWN="deepgram groq" run); rc=$?; chk "оба недоступны — обе причины названы, код 1 (не «пусто»)" '[ $rc = 1 ] && echo "$o" | grep -q "Deepgram: сервис не ответил" && echo "$o" | grep -q "Groq: сервис не ответил" && ! echo "$o" | grep -q "\[empty\]"' 'echo "rc=$rc $o"'
o=$(NET_DOWN=groq DG_SAYS="salom" DG_CONF=0.31 run); rc=$?; chk "Groq недоступен, Deepgram не уверен — причина в журнале и текст Deepgram, код 0" '[ $rc = 0 ] && echo "$o" | grep -q "Groq: сервис не ответил" && echo "$o" | grep -q "^salom$"' 'echo "rc=$rc $o"'
rm "$T/sec/groq.env"
o=$(NET_DOWN=deepgram run); rc=$?; chk "только Deepgram и он недоступен — причина названа, код 1" '[ $rc = 1 ] && echo "$o" | grep -q "Deepgram: сервис не ответил"' 'echo "rc=$rc $o"'
rm "$T/sec/deepgram.env"; printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"
o=$(NET_DOWN=groq run); rc=$?; chk "только Groq и он недоступен — причина названа, код 1" '[ $rc = 1 ] && echo "$o" | grep -q "Groq: сервис не ответил"' 'echo "rc=$rc $o"'
o=$(run); rc=$?; chk "контроль: сеть есть — текст Groq, причин в журнале нет" '[ $rc = 0 ] && [ "$o" = "salom dunyo" ]' 'echo "rc=$rc $o"'
echo "итог $ok/$n"; [ $ok -eq $n ]
