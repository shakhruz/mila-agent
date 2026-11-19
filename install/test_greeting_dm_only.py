#!/usr/bin/env python3
"""The first-day greeting and getting acquainted are for the owner's private chat only, once: the home's CLAUDE.md and the
group skill must say so in the places Mila reads when she is added to a group. Without these lines a newborn Mila greeted a
group with «I was just born». Texts only — the live behaviour is checked by an exam on a stand.
Run: python3 test_greeting_dm_only.py [kit_root]"""
import os, re, sys
KIT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:200]))
rd = lambda f: open(os.path.join(KIT, f), encoding="utf-8").read()
def section(text, title):
    m = re.search(r"^## " + re.escape(title) + r".*?(?=^## |\Z)", text, re.S | re.M); return " ".join(m.group(0).split()) if m else ""
cl = rd("templates/work/CLAUDE.md"); first = section(cl, "The first conversation"); groups = section(cl, "Groups")
check("CLAUDE.md: «first conversation» and «Groups» sections exist", first and groups)
check("first conversation: «ANY message» is scoped to the private chat", re.search(r"ANY message from my owner in our private chat", first), first[:160])
check("first conversation: no bare «ANY message from my owner —» (the old, unscoped rule)", "ANY message from my owner —" not in first)
check("first conversation: in a group — never, even before the line in USER.md", "in a group I never get acquainted" in first and "even while that line is not in `USER.md` yet" in first)
check("Groups: added to a group → mila-in-chat, silence, one line with my own name", "`mila-in-chat`" in groups and "stay silent" in groups and "my own name" in groups)
check("Groups: greeting and acquaintance are for the private chat only", "private chat only" in groups)
chat = " ".join(rd("skills/mila-in-chat/SKILL.md").split())
check("mila-in-chat: the first-day greeting never goes to a group", "в группу не несу никогда" in chat and "только для лички хозяина" in chat)
check("mila-in-chat: acquaintance not finished → same silence until the button", "Знакомство ещё не пройдено" in chat and "молчу до его кнопки" in chat)
check("onboarding: private chat only", "private chat only" in " ".join(rd("skills/onboarding/SKILL.md").split()))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
