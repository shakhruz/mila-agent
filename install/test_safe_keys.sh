#!/bin/bash
# Слух и топливо берут ключ из env, иначе из сейфа work/secrets/<имя>.env (600); файл 644 — отказ; env важнее файла.
# Ключ в Authorization видит только поддельный curl. bash install/test_safe_keys.sh
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
mkdir -p "$T/bin" "$T/sec"
cat > "$T/bin/curl" <<'C'
#!/bin/bash
for a in "$@"; do case "$a" in Authorization:*) printf '%s\n' "$a" >> "$CURL_LOG";; esac; done
case "$*" in *transcriptions*) echo '{"language":"russian","text":"привет"}';; *) echo '{"data":{"limit":5,"usage":1}}';; esac
C
chmod +x "$T/bin/curl"; export PATH="$T/bin:$PATH" SAFE_DIR="$T/sec" CURL_LOG="$T/auth.log" HOME="$T"
GK="gsk""_file""$RANDOM""xyz"; EK="gsk""_env""$RANDOM""abc"; OK_="sk-""or-v1-file""$RANDOM"
umask 077; printf "GROQ_API_KEY='%s'\n" "$GK" > "$T/sec/groq.env"; printf "OPENROUTER_API_KEY='%s'\n" "$OK_" > "$T/sec/openrouter.env"
: > "$T/a.ogg"
out=$(env -u GROQ_API_KEY bash "$H/install/transcribe-voice.sh" "$T/a.ogg" 2>&1)
chk "слух: env пуст, groq.env 600 → ключ из сейфа, расшифровка есть" "grep -q 'Bearer $GK' '$T/auth.log' && [ \"\$(echo '$out')\" = привет ]"
chk "слух: значение ключа не в выводе" "! echo '$out' | grep -q '$GK'"
: > "$T/auth.log"; GROQ_API_KEY="$EK" bash "$H/install/transcribe-voice.sh" "$T/a.ogg" >/dev/null 2>&1
chk "слух: env важнее файла" "grep -q 'Bearer $EK' '$T/auth.log' && ! grep -q '$GK' '$T/auth.log'"
chmod 644 "$T/sec/groq.env"; : > "$T/auth.log"
err=$(env -u GROQ_API_KEY bash "$H/install/transcribe-voice.sh" "$T/a.ogg" 2>&1 >/dev/null); rc=$?
chk "слух: groq.env 644 → отказ, в сеть не ходим" "[ $rc -ne 0 ] && echo '$err' | grep -q 'открыт другим' && [ ! -s '$T/auth.log' ]"
# руками: двойные кавычки, CRLF, пробел в конце, export, пробелы вокруг «=» — ключ в заголовке ровно тот же
i=0; for form in "GROQ_API_KEY=\"$GK\"" "GROQ_API_KEY=$GK"$'\r' "GROQ_API_KEY=$GK " "export GROQ_API_KEY=$GK" "GROQ_API_KEY = $GK"; do
  i=$((i+1)); printf '%s\n' "$form" > "$T/sec/groq.env"; chmod 600 "$T/sec/groq.env"; : > "$T/auth.log"
  env -u GROQ_API_KEY bash "$H/install/transcribe-voice.sh" "$T/a.ogg" >/dev/null 2>&1
  chk "слух: ручная форма $i — в заголовке ровно ключ" "[ \"\$(cat '$T/auth.log')\" = 'Authorization: Bearer $GK' ]"
done
printf 'GROQ_API_KEY=old%s\nGROQ_API_KEY=%s\n' "$RANDOM" "$GK" > "$T/sec/groq.env"; : > "$T/auth.log"
env -u GROQ_API_KEY bash "$H/install/transcribe-voice.sh" "$T/a.ogg" >/dev/null 2>&1
chk "слух: две строки поля — берётся последняя (как read_safe)" "[ \"\$(cat '$T/auth.log')\" = 'Authorization: Bearer $GK' ]"
rm -f "$T/sec/groq.env"
chk "слух: нигде нет ключа → понятная строка" "env -u GROQ_API_KEY bash '$H/install/transcribe-voice.sh' '$T/a.ogg' 2>&1 | grep -q 'ни в env, ни в сейфе'"
: > "$T/auth.log"; f=$(env -u OPENROUTER_API_KEY -u ANTHROPIC_BASE_URL sh "$H/skills/onboarding/fuel.sh" 2>&1)
chk "топливо: env пуст, openrouter.env 600 → ключ из сейфа" "grep -q 'Bearer $OK_' '$T/auth.log' && echo '$f' | grep -q '^FUEL'"
chk "топливо: значение ключа не в выводе" "! echo '$f' | grep -q '$OK_'"
chmod 644 "$T/sec/openrouter.env"; : > "$T/auth.log"
f=$(env -u OPENROUTER_API_KEY -u ANTHROPIC_BASE_URL sh "$H/skills/onboarding/fuel.sh" 2>&1)
chk "топливо: openrouter.env 644 → отказ, FUEL unknown, в сеть не ходим" "echo '$f' | grep -q 'FUEL unknown' && [ ! -s '$T/auth.log' ]"
echo "итог $ok/$n"; [ $ok -eq $n ]
