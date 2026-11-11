#!/usr/bin/env python3
"""tg_md2.py: plain text for MarkdownV2 — every special character is escaped, the backslash itself too (a path like C:\\dir or a
«\\n» typed by a person must not eat the next character or break the message); inside a copy block only ` and \\ are escaped.
Run: python3 skills/copyblock/test_tg_md2.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_md2 as M
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + repr(x)))
chk("a backslash in plain text is escaped", M.esc("C:\\dir") == "C:\\\\dir", M.esc("C:\\dir"))
chk("a backslash before a special character: both escaped, nothing swallowed", M.esc("a\\.b") == "a\\\\\\.b", M.esc("a\\.b"))
chk("every special character of MarkdownV2 gets a backslash", all(M.esc(c) == "\\" + c for c in "_*[]()~`>#+-=|{}.!"))
chk("letters, digits, spaces and Cyrillic stay as they are", M.esc("Привет, мир 42") == "Привет, мир 42")
chk("a copy block escapes only ` and the backslash", M.code_block("a.b`c\\d") == "```\na.b\\`c\\\\d\n```", M.code_block("a.b`c\\d"))
chk("build joins parts with an empty line and drops empty ones", M.build("a", "", "b") == "a\n\nb")
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
