#!/bin/bash
# run_all.sh names the place of a failure by itself: under a failed test it prints that test's own ❌ lines (or the tail of its
# output when there are none); a green test stays one line. A red run in CI is read without logging into the machine.
# bash tests/test_run_all_show.sh
set -u; H="$(cd "$(dirname "$0")/.." && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
R="$T/repo"; mkdir -p "$R/tests" "$R/tools" "$R/skills" "$R/templates" "$R/packs"; cp "$H/tests/run_all.sh" "$R/tests/"
printf '#!/bin/bash\necho "✅ первое"\necho "итог 1/1"\n' > "$R/tests/test_good.sh"
BAD='плохо'; MARK='вот это место упало'
printf '#!/bin/bash\necho "✅ раз"\necho "%s %s"\necho "✅ три"\necho "итог 2/3"\nexit 1\n' "$(printf '\342\235\214')" "$MARK" > "$R/tests/test_bad.sh"
printf '#!/bin/bash\necho "строка до"\necho "последняя строка без значка: %s"\nexit 3\n' "$BAD" > "$R/tests/test_crash.sh"
printf 'print("итог 1/1")\n' > "$R/tools/check_frontmatter.py"; printf 'print("итог 1/1")\n' > "$R/tools/kitchen_lint.py"
git -C "$R" init -q; git -C "$R" add -A; git -C "$R" -c user.email=t@example.com -c user.name=t commit -qm x
out=$(cd "$R" && env -u CI bash tests/run_all.sh 2>&1); rc=$?
printf '%s\n' "$out" > "$T/out.txt"
chk "упавший тест: итог красный, код 1, названы оба упавших" "[ $rc -eq 1 ] && grep -q 'FAILED 2/5: bash tests/test_bad.sh bash tests/test_crash.sh' $T/out.txt"
chk "под упавшим тестом — его собственная строка с местом падения, с отступом" "grep -q '^      .*$MARK' $T/out.txt"
chk "зелёные строки упавшего теста под ним не печатаются" "! grep -q '^      .*✅' $T/out.txt"
chk "тест упал без значков — под ним хвост его вывода" "grep -q '^      последняя строка без значка: $BAD' $T/out.txt && grep -q '^      строка до' $T/out.txt"
chk "зелёный тест — одна строка, без раскрытия" "[ \$(grep -c 'test_good.sh' $T/out.txt) -eq 1 ] && ! grep -q '^      .*первое' $T/out.txt"
printf '#!/bin/bash\necho "итог 1/1"\n' > "$R/tests/test_bad.sh"; printf '#!/bin/bash\necho "итог 1/1"\n' > "$R/tests/test_crash.sh"
out=$(cd "$R" && env -u CI bash tests/run_all.sh 2>&1); rc=$?; printf '%s\n' "$out" > "$T/out2.txt"
chk "все зелёные — ALL GREEN, код 0, ни одной раскрытой строки" "[ $rc -eq 0 ] && grep -q 'ALL GREEN · 5' $T/out2.txt && ! grep -q '^      ' $T/out2.txt"
echo "итог $ok/$n"; [ $ok -eq $n ]
