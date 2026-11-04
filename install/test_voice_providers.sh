#!/bin/bash
# Голос: Deepgram первым (nova-3, multi), Groq вторым; ключи из env или сейфа; уверенный Deepgram — его текст; неуверенный
# (узбекский у Deepgram нет) — Groq, если его ключ есть, иначе текст Deepgram. Сеть подменена: поддельный curl.
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1  ← $(eval "$3" 2>&1 | head -c 200)"; fi; }
mkdir -p "$T/bin" "$T/sec"
cat > "$T/bin/curl" <<'C'
#!/bin/bash
for a in "$@"; do case "$a" in Authorization:*) printf '%s\n' "$a" >> "$CURL_LOG";; esac; done
case "$*" in
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
o=$(DG_CODE=402 run); chk "Deepgram 402 — «кончился кредит»" 'echo "$o" | grep -q "кончился кредит"' 'echo "$o"'
o=$(DG_CODE=429 run); chk "Deepgram 429 — «лимит запросов»" 'echo "$o" | grep -q "лимит запросов"' 'echo "$o"'
printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"
o=$(DG_CODE=401 run); chk "Deepgram 401, есть Groq — ответ Groq" 'echo "$o" | tail -1 | grep -q "salom dunyo"' 'echo "$o"'
rm "$T/sec/deepgram.env"; o=$(run); chk "только Groq (как во флоте) — путь прежний" '[ "$o" = "salom dunyo" ]' 'echo "$o"'
rm "$T/sec/groq.env"; o=$(run); chk "ни одного ключа — понятная строка и код 1" 'echo "$o" | grep -q "нет ключа распознавания"' 'echo "$o"'
o=$(DEEPGRAM_API_KEY="dg_env_1" DG_SAYS="ok" DG_CONF=0.9 bash "$H/install/transcribe-voice.sh" "$T/a.ogg" 2>&1); chk "ключ Deepgram из env" '[ "$o" = "ok" ]' 'echo "$o"'
echo "итог $ok/$n"; [ $ok -eq $n ]
