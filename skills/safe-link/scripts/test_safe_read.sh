#!/bin/bash
# safe_read.py: --check показывает наличие полей и маску, значений нет; открытый сейф (644) — отказ; нет сейфа — подсказка. Номер карты
# собирается в тесте. bash skills/safe-link/scripts/test_safe_read.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export SAFE_DIR=$T; R="python3 -I $H/safe_read.py"
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
P=$(python3 -c "
import random;d=[8,6,0,0]+[random.randint(0,9) for _ in range(11)]
t=sum((x*2-9 if x*2>9 else x*2) if i%2==0 else x for i,x in enumerate(reversed(d)));print(''.join(map(str,d))+str((10-t%10)%10))")
PW="pw$RANDOM$RANDOM"
umask 077; printf "SITE_LOGIN='998901112233'\nSITE_PASSWORD='%s'\nCARD_NUMBER='%s'\nCARD_EXPIRY='0828'\n" "$PW" "$P" > $T/login.env
out=$($R login --check SITE_LOGIN,SITE_PASSWORD,CARD_NUMBER,CARD_EXPIRY)
chk "все поля есть, ok" "echo '$out' | grep -q '\"ok\": true'"
chk "маска карты ****1234 и логина 998…, значений нет" "echo '$out' | grep -q '\\*\\*\\*\\*${P: -4}' && echo '$out' | grep -q '998…' && ! echo '$out' | grep -q '$PW' && ! echo '$out' | grep -q '$P'"
chk "нет поля — в «нет»" "$R login --check API_KEY | grep -q '\"нет\": \\[\"API_KEY\"\\]'"
chmod 644 $T/login.env
chk "сейф открыт для других — отказ" "! $R login --check CARD_NUMBER"
chk "нет сейфа — подсказка попросить ссылку" "$R nosuch --check X | grep -q 'попросить ссылку сейфа'"
chk "без --check — значений не печатает (справка)" "! $R login 2>&1 | grep -q '$PW'"
# --- the mask goes by whole segments of the field name: a field that is a secret by its last word (password, key, token, PIN…)
# shows dots only, even when its name also has USER / EMAIL / PAN in it; a short value is never shown in part
chmod 600 $T/login.env
V1="Zq9-$RANDOM-word"; V2="Kx7-$RANDOM-mail"; V3="live-$RANDOM$RANDOM-abc"; V4="tok-$RANDOM$RANDOM"
printf "USER_PASSWORD='%s'\nEMAIL_PASSWORD='%s'\nCOMPANY_API_KEY='%s'\nPAN_TOKEN='%s'\nSITE_LOGIN='ab'\nSHORT_CARD_NUMBER='12'\nCARD_NUMBER='%s'\nPLAIN_LOGIN='abcdef'\n" "$V1" "$V2" "$V3" "$V4" "$P" > $T/k.env
o=$($R k --check USER_PASSWORD,EMAIL_PASSWORD,COMPANY_API_KEY,PAN_TOKEN,SITE_LOGIN,CARD_NUMBER,PLAIN_LOGIN)
chk "secret by name (password, key, token) — dots only, no piece of the value" "echo '$o' | grep -q '••••' && ! echo '$o' | grep -q -E 'Zq9|Kx7|live|tok-|${V4: -4}'"
chk "control: CARD_NUMBER still ****last4, PLAIN_LOGIN still abc…" "echo '$o' | grep -q '\\*\\*\\*\\*${P: -4}' && echo '$o' | grep -q 'abc…'"
chk "short values are not shown in part (login of 2 chars, card of 2 digits)" "! echo '$o' | grep -q '\"ab…\"' && ! $R k --check SHORT_CARD_NUMBER | grep -q '\\*\\*\\*\\*12'"
ln -s $T/k.env $T/lnk.env
chk "a safe that is a symlink — refused" "$R lnk --check SITE_LOGIN | grep -q 'ссылка или путь вне'"
printf 'A=\xff\xfe\n' > $T/bin.env
chk "broken UTF-8 — a JSON refusal, no traceback" "! $R bin --check A 2>&1 | grep -q Traceback && $R bin --check A | grep -q 'не читается'"
chk "empty --check — refused" "$R k --check '' | grep -q 'не указаны поля'"
chk "--check with no argument — refused, no traceback" "! $R k --check 2>&1 | grep -q Traceback"
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
