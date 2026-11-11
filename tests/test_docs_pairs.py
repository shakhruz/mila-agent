#!/usr/bin/env python3
"""Docs pages come in pairs: X.md (English, the main one) and X.ru.md. Every .ru.md has its English twin; the pages of PAIRS
have both; the two point at each other in the first lines; they have the same number of sections, table rows and code blocks
(a section added to one language only is a failure); every relative link leads to a file; every repo path named in the
«In the code» table exists; the Scheduler's numbers in the page are the numbers in the code.
Run: python3 tests/test_docs_pairs.py"""
import os, re, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(REPO, "docs")
PAIRS = ["SCHEDULER", "CONCEPTS"]          # pages written as pairs from the start; older pairs are checked for the twin and the links only
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
def read(name): return open(os.path.join(D, name), encoding="utf-8").read()
def shape(t):
    body = re.sub(r"```.*?```", "", t, flags=re.S)
    return {"sections": len(re.findall(r"^## ", body, re.M)), "table rows": len(re.findall(r"^\|", body, re.M)),
            "code blocks": len(re.findall(r"^```", t, re.M)) // 2, "bullets": len(re.findall(r"^- ", body, re.M))}
def links(t): return [x for x in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", t) if not re.match(r"[a-z]+:", x)]

ru = sorted(f[:-6] for f in os.listdir(D) if f.endswith(".ru.md"))
chk("у каждой русской страницы есть английская пара", all(os.path.isfile(os.path.join(D, x + ".md")) for x in ru), ru)
chk("страницы-пары на месте: " + ", ".join(PAIRS), all(os.path.isfile(os.path.join(D, x + s)) for x in PAIRS for s in (".md", ".ru.md")))
for x in sorted(set(ru) | set(PAIRS)):
    if not all(os.path.isfile(os.path.join(D, x + s)) for s in (".md", ".ru.md")): continue
    en, r = read(x + ".md"), read(x + ".ru.md")
    chk(x + ": страницы ссылаются друг на друга в первых строках", "](%s.ru.md)" % x in "\n".join(en.split("\n")[:5]) and "](%s.md)" % x in "\n".join(r.split("\n")[:5]))
    for name, t in ((x + ".md", en), (x + ".ru.md", r)):
        dead = [l for l in links(t) if not os.path.exists(os.path.normpath(os.path.join(D, l)))]
        chk(name + ": каждая ссылка ведёт к файлу", not dead, dead)
for x in PAIRS:
    en, r = read(x + ".md"), read(x + ".ru.md")
    chk(x + ": в двух языках поровну разделов, строк таблиц, блоков кода и пунктов", shape(en) == shape(r), (shape(en), shape(r)))
    chk(x + ": русская страница написана по-русски, английская — по-английски", len(re.findall(r"[а-яё]", r, re.I)) > 5 * len(re.findall(r"[а-яё]", en, re.I)) and len(re.findall(r"[а-яё]", r, re.I)) > 500)
    for name, t, head in ((x + ".md", en, "## In the code"), (x + ".ru.md", r, "## В коде")):
        part = t.split(head, 1)[1].split("\n## ", 1)[0] if head in t else ""
        paths = [p for p in re.findall(r"`([^`\s]+)`", part) if "/" in p]
        gone = [p for p in paths if not os.path.exists(os.path.join(REPO, p))]
        chk(name + ": таблица «в коде» есть, и каждый названный в ней путь существует (%d)" % len(paths), len(paths) >= 4 and not gone, gone)
    blocks = lambda t: re.findall(r"```(?:bash)?\n(.*?)```", t, re.S)
    cmds = lambda t: [re.sub(r"\s+#.*$|\"[^\"]*\"|YYYY-MM-DD|ГГГГ-ММ-ДД", "", l).strip() for b in blocks(t) for l in b.split("\n") if l.startswith(("python3 ", "M="))]
    chk(x + ": команды в блоках кода одни и те же в двух языках", cmds(en) == cmds(r), (cmds(en), cmds(r)))

# the Scheduler's numbers are the code's numbers
src = open(os.path.join(REPO, "skills", "raspisanie", "mila_cron.py"), encoding="utf-8").read()
m = re.search(r"^MAX_JOBS, MAX_TEXT, DEF_DAYS, MAX_DAYS = (\d+), (\d+), (\d+), (\d+)$", src, re.M)
chk("пределы задач найдены в коде", bool(m))
if m:
    jobs, text, days, top = m.groups()
    for name, want in (("SCHEDULER.md", ("at most %s" % jobs, "1–%s characters" % text, "%s days by default, %s at most" % (days, top))),
                       ("SCHEDULER.ru.md", ("не больше %s" % jobs, "1–%s знаков" % text, "%s дней по умолчанию, не больше %s" % (days, top)))):
        t = read(name); miss = [w for w in want if w not in t]
        chk(name + ": число задач, длина текста и срок жизни — как в коде", not miss, miss)
bar = open(os.path.join(REPO, "install", "baraban.py"), encoding="utf-8").read()
spec = open(os.path.join(REPO, "skills", "raspisanie", "cronspec.py"), encoding="utf-8").read()
chk("пояс и тихие часы по умолчанию на странице — как в службе", 'DEFAULT_TZ = "Asia/Tashkent"' in spec and "else 22–08" in bar and all("Asia/Tashkent" in read(f) and "22–08" in read(f) for f in ("SCHEDULER.md", "SCHEDULER.ru.md")))
inst = open(os.path.join(REPO, "install", "install.sh"), encoding="utf-8").read()
chk("страница говорит о таймере на ноутбуке то, что делает установщик: ставит — и названы те же имена служб", ("baraban.py" in inst) == ("the installer sets a pass every minute" in read("SCHEDULER.md"))
    and all(x in inst and x in read(f) for x in ("com.milagpt.scheduler", "mila-scheduler") for f in ("SCHEDULER.md", "SCHEDULER.ru.md")))
chk("срок свежести отметки прохода на странице — как в коде (пять минут), папки отметок названы те же", "BEAT_FRESH = 300" in spec and "five minutes" in read("SCHEDULER.md") and "пяти минут" in read("SCHEDULER.ru.md")
    and all(x in spec and x in read("SCHEDULER.md") for x in ("/run/mila/scheduler", "MILA_SCHEDULER_BEAT")))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
