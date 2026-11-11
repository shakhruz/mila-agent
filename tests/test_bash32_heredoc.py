#!/usr/bin/env python3
"""bash 3.2 — the system shell of macOS — counts the apostrophes of a here-document that stands inside a command substitution
$( … <<'X' … X ): an unpaired one (a comment with «it's») ends the script with «unexpected EOF while looking for matching».
The installer must not have such a block at all; in every other tracked shell script the apostrophes inside such a block are paired.
Run: python3 tests/test_bash32_heredoc.py [file …]"""
import os, re, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPEN = re.compile(r"""\$\([^)]*<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1""")
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))


def blocks(text):
    """→ [(line of the opening, delimiter, [body lines])] for here-documents opened inside $( on the same line."""
    L = text.split("\n"); out = []; i = 0
    while i < len(L):
        m = OPEN.search(L[i])
        if m:
            j = i + 1
            while j < len(L) and L[j].strip() != m.group(2): j += 1
            out.append((i + 1, m.group(2), L[i + 1:j])); i = j
        i += 1
    return out


def odd(text):
    return [(ln, d, [b for b in body if b.count("'") % 2][:3]) for ln, d, body in blocks(text) if sum(b.count("'") for b in body) % 2]


def shell_files():
    names = subprocess.run(["git", "-C", REPO, "ls-files"], capture_output=True, text=True).stdout.split("\n")
    out = []
    for f in names:
        p = os.path.join(REPO, f)
        if not f or not os.path.isfile(p): continue
        if f.endswith(".sh"): out.append(f); continue
        try:
            with open(p, "rb") as fh: head = fh.readline(80)
        except OSError: continue
        if head.startswith(b"#!") and (b"bash" in head or head.rstrip().endswith(b"/sh")): out.append(f)
    return out


if len(sys.argv) > 1:
    for f in sys.argv[1:]:
        print(f, odd(open(f, encoding="utf-8", errors="replace").read()) or "чисто")
    sys.exit(0)
# the rule on samples first: it sees the trap and does not see what is fine
BAD = 'X="$(python3 - << \'PY\'\n# the guard checks a topic\'s name\nprint(1)\nPY\n)"\n'
chk("ловушка видна: непарный апостроф в комментарии внутри $( <<'PY' )", [x[0] for x in odd(BAD)] == [1], odd(BAD))
chk("два апострофа в блоке — пара, не находка (так bash 3.2 и проходил раньше)", not odd(BAD.replace("print(1)", "print('a')  # it's")), odd(BAD.replace("print(1)", "print('a')  # it's")))
chk("here-document вне $( ) с непарным апострофом — не находка", not odd("python3 - > \"$T\" << 'PY'\n# a topic's name\nPY\nX=\"$(cat \"$T\")\"\n"))
chk("метка без кавычек и с дефисом (<<-EOF) тоже разбирается", [x[1] for x in odd("Y=$(cat <<-EOF\n\tdon't\n\tEOF\n)\n")] == ["EOF"], odd("Y=$(cat <<-EOF\n\tdon't\n\tEOF\n)\n"))
files = shell_files()
chk("скрипты оболочки найдены (%d)" % len(files), len(files) >= 20 and "install/install.sh" in files and "install/get.sh" in files, len(files))
for f in ("install/install.sh", "install/get.sh"):
    b = blocks(open(os.path.join(REPO, f), encoding="utf-8").read())
    chk(f + ": here-document внутри $( ) нет вовсе — установщик идёт под bash 3.2 на каждом Маке", not b, [(x[0], x[1]) for x in b])
found = {f: odd(open(os.path.join(REPO, f), encoding="utf-8", errors="replace").read()) for f in files}
found = {f: v for f, v in found.items() if v}
chk("ни в одном скрипте нет блока $( <<X ) с непарным апострофом", not found, found)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
