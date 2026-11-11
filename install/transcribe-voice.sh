#!/bin/bash
# transcribe-voice.sh <audiofile> — расшифровка голосового в контейнере Компаньона (14.09.2026).
# Groq whisper-large-v3 с автоопределением языка и вторым проходом на узбекском —
# та же схема, что у администратора на Маке и у агентов. Ключ — GROQ_API_KEY из env, иначе из сейфа work/secrets/groq.env (600).
# Никогда не печатает ключ. Пусто → "[empty]" (приёмник покажет «расшифровка пустая»).
set -euo pipefail
[ -n "${1:-}" ] || { echo "usage: transcribe-voice.sh <audiofile>" >&2; exit 1; }
# Hearing is a connector the owner can switch off (skills/konnektory: `connectors.py off sluh` leaves this flag): then nothing is
# sent to any speech service, whatever keys are in the safe.
if [ -e "${MILA_WORK:-$HOME/work}/connectors/sluh.off" ]; then echo "[слух выключен хозяином — голосовое не расшифровываю]" >&2; exit 1; fi
# Ключ из сейфа work/secrets/<имя>.env, если в env пусто (env важнее файла — как vault.py). Файл открыт группе/другим — не читаю.
safe_key() { _f="${SAFE_DIR:-$HOME/work/secrets}/$1.env"; [ -f "$_f" ] || return 1
  _m=$(stat -c %a "$_f" 2>/dev/null || stat -f %Lp "$_f"); case "$_m" in *00) ;; *) echo "[сейф $1 открыт другим ($_m) — не читаю]" >&2; return 1;; esac
  tr -d '\r' < "$_f" | sed -n -E "s/^[[:space:]]*(export[[:space:]]+)?$2[[:space:]]*=[[:space:]]*//p" | tail -n 1 |   # последняя строка — как dotenv и read_safe
    sed -E "s/[[:space:]]+\$//; s/^'(.*)'\$/\1/; s/^\"(.*)\"\$/\1/"; }   # руками пишут по-разному: CRLF, пробелы, export, "…"
SRC="$1"
# Deepgram first (nova-3, language=multi; a key is issued at once, $200 trial credit), Groq second (whisper; Uzbek — Deepgram has
# none). Deepgram's answer is taken when it is sure (confidence ≥ 0.6); otherwise — Groq if its key is there, else Deepgram's text.
DG="${DEEPGRAM_API_KEY:-}"
[ -n "$DG" ] || DG=$(safe_key deepgram DEEPGRAM_API_KEY || true)
KEY="${GROQ_API_KEY:-}"
[ -n "$KEY" ] || KEY=$(safe_key groq GROQ_API_KEY || true)
# The key keeper (Mila Agent): the keys are with it, the request goes through it with a placeholder — this script never holds a key.
if [ -n "${MILA_KEYD:-}" ] && ST_=$(curl -s --max-time 5 "$MILA_KEYD/status"); then
  case "$ST_" in *'"deepgram": true'*) DG=mila-keyd; DEEPGRAM_API="$MILA_KEYD/deepgram" ;; esac
  case "$ST_" in *'"groq": true'*) KEY=mila-keyd; GROQ_API="$MILA_KEYD/groq" ;; esac
fi
[ -n "$DG$KEY" ] || { echo "[нет ключа распознавания: ни Deepgram, ни Groq — ни в env, ни в сейфе]" >&2; exit 1; }
DG_TEXT=""
if [ -n "$DG" ]; then
  # the key goes in a header read from stdin (-H @-), not in curl's arguments — those are visible to other processes (ps)
  DG_RAW=$(printf 'Authorization: Token %s\n' "$DG" | curl -s --max-time 90 -w '\n%{http_code}' -X POST "${DEEPGRAM_API:-https://api.deepgram.com}/v1/listen?model=nova-3&language=multi&smart_format=true" \
    -H @- -H "Content-Type: audio/ogg" --data-binary "@$SRC")
  DG_CODE="${DG_RAW##*$'\n'}"; DG_BODY="${DG_RAW%$'\n'*}"
  case "$DG_CODE" in   # the reason goes to stderr (the receiver's log), never the key
    401|403) echo "[Deepgram: ключ не принят (HTTP $DG_CODE) — нужен новый ключ]" >&2 ;;
    402) echo "[Deepgram: на счёте кончился кредит (HTTP 402)]" >&2 ;;
    429) echo "[Deepgram: лимит запросов (HTTP 429), позже]" >&2 ;;
    200) ;;
    *) echo "[Deepgram: ответ HTTP ${DG_CODE:-нет}]" >&2 ;;
  esac
  if [ "$DG_CODE" != 200 ] && [ -z "$KEY" ]; then exit 1; fi   # no Groq to fall back on: the receiver says «transcription failed»
  DG_OUT=$(printf '%s' "$DG_BODY" | python3 -c '
import json, sys
try:
    a = json.load(sys.stdin)["results"]["channels"][0]["alternatives"][0]
    print("%.2f\t%s" % (float(a.get("confidence") or 0), (a.get("transcript") or "").strip()))
except Exception:
    print("0\t")')
  DG_CONF="${DG_OUT%%$'\t'*}"; DG_TEXT="${DG_OUT#*$'\t'}"
  if [ -n "$DG_TEXT" ] && python3 -c "import sys; sys.exit(0 if float('$DG_CONF') >= 0.6 else 1)"; then
    printf '%s\n' "$DG_TEXT"; exit 0
  fi
  if [ -z "$KEY" ]; then
    [ -n "$DG_TEXT" ] && { printf '%s\n' "$DG_TEXT"; exit 0; }
    echo "[empty]"; exit 0
  fi
fi
API="${GROQ_API:-https://api.groq.com}/openai/v1/audio/transcriptions"
case "$SRC" in
  *.oga) TMP="$(mktemp -t voiceXXXX).ogg"; cp "$SRC" "$TMP"; trap 'rm -f "$TMP"' EXIT; SRC="$TMP" ;;
esac
ask() {
  if [ -n "${2:-}" ]; then
    printf 'Authorization: Bearer %s\n' "$KEY" | curl -s --max-time 90 -X POST "$API" -H @- -F "file=@$1" -F "model=whisper-large-v3" -F "language=$2" -F "response_format=verbose_json"
  else
    printf 'Authorization: Bearer %s\n' "$KEY" | curl -s --max-time 90 -X POST "$API" -H @- -F "file=@$1" -F "model=whisper-large-v3" -F "response_format=verbose_json"
  fi
}
pick() { python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("\t"); sys.exit()
print((d.get("language") or "") + "\t" + (d.get("text") or "").strip())'; }
OUT=$(ask "$SRC" "" | pick)
LANG="${OUT%%$'\t'*}"; TEXT="${OUT#*$'\t'}"
case "$LANG" in
  uzbek|uz|azerbaijani|az|kazakh|kk|kyrgyz|ky|turkmen|tk|tatar|tt|turkish|tr|bashkir|ba|tajik|tg|uighur|ug|chuvash|cv|"")
    OUT2=$(ask "$SRC" "uz" | pick); TEXT2="${OUT2#*$'\t'}"; [ -n "$TEXT2" ] && TEXT="$TEXT2" ;;
esac
[ -z "$TEXT" ] && TEXT="$DG_TEXT"   # Groq said nothing — Deepgram's unsure text is better than none
# D-NNNN (10.10): whisper путает имена продукта («Милодипити.io», «Milo Companion», «хайку 55»).
# Подсказка prompt проверена и отвергнута: на голосовом 835 съела 30 % текста и вставила себя в ответ.
# Поэтому только точная замена известных искажений после расшифровки; смысл не трогаем.
TEXT=$(printf '%s' "$TEXT" | python3 -c '
import re, sys
t = sys.stdin.read()
for a, b in [
    (r"(?i)\bмилодипити\.?\s*io\b", "milagpt.io"), (r"(?i)\bмилодипити\b", "MilaGPT"),
    (r"(?i)\b(?:mewl|meal|milo|mela)\s?gpt\b", "MilaGPT"), (r"(?i)\bмила\s?(?:гпт|джипити|джи пи ти)\b", "MilaGPT"),
    (r"\bMilo (Companion|Telegram|Pay)\b", r"Mila \1"), (r"(?i)\bхайку\s*5[.,]?5\b", "Haiku 5.5"),
]:
    t = re.sub(a, b, t)
sys.stdout.write(t)')
[ -n "$TEXT" ] && printf '%s\n' "$TEXT" || echo "[empty]"
