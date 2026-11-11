#!/usr/bin/env python3
"""Docs pages come in pairs: X.md (English, the main one) and X.ru.md. Every .ru.md has its English twin; the pages of PAIRS
have both; the two point at each other in the first lines; they have the same number of sections, table rows and code blocks
(a section added to one language only is a failure); every relative link leads to a file; every repo path named in the
«In the code» table exists; the Scheduler's numbers in the page are the numbers in the code.
Run: python3 tests/test_docs_pairs.py"""
import os, re, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(REPO, "docs")
PAIRS = ["SCHEDULER", "CONCEPTS", "MODULES", "MIND", "design/PASSPORT"]          # pages written as pairs from the start; older pairs are checked for the twin and the links only
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

ru = sorted(os.path.relpath(os.path.join(r0, f), D)[:-6] for r0, _, fs in os.walk(D) for f in fs if f.endswith(".ru.md"))      # with subfolders: design/…
chk("у каждой русской страницы есть английская пара", all(os.path.isfile(os.path.join(D, x + ".md")) for x in ru), ru)
chk("страницы-пары на месте: " + ", ".join(PAIRS), all(os.path.isfile(os.path.join(D, x + s)) for x in PAIRS for s in (".md", ".ru.md")))
for x in sorted(set(ru) | set(PAIRS)):
    if not all(os.path.isfile(os.path.join(D, x + s)) for s in (".md", ".ru.md")): continue
    en, r = read(x + ".md"), read(x + ".ru.md")
    b0 = os.path.basename(x)
    chk(x + ": страницы ссылаются друг на друга в первых строках", "](%s.ru.md)" % b0 in "\n".join(en.split("\n")[:5]) and "](%s.md)" % b0 in "\n".join(r.split("\n")[:5]))
    for name, t in ((x + ".md", en), (x + ".ru.md", r)):
        dead = [l for l in links(t) if not os.path.exists(os.path.normpath(os.path.join(D, os.path.dirname(x), l)))]
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
# the map of modules: fifteen, every named path exists, the state marks are the four of the legend and nothing else
MARKS = {"MODULES.md": ("in the core", "accepted, awaits release", "in development", "as a pack"), "MODULES.ru.md": ("в ядре", "принято, ждёт выпуска", "в разработке", "паком")}
for name, marks in MARKS.items():
    t = read(name)
    heads = re.findall(r"^## (\d+)\. ", t, re.M)
    chk(name + ": пятнадцать модулей, по порядку", heads == [str(i) for i in range(1, 16)], heads)
    paths = [p for p in re.findall(r"`([^`\s]+)`", t) if "/" in p]
    gone = [p for p in paths if not os.path.exists(os.path.join(REPO, p))]
    chk(name + ": каждый названный путь существует (%d)" % len(paths), len(paths) >= 40 and not gone, gone)
    used = re.findall(r"^- \*\*([^*]+)\*\*", t, re.M)
    allowed = set(marks) | {marks[2] + ", " + marks[3]}          # «in development, as a pack» — a pack that is not written yet
    odd = [u for u in used if u not in allowed]
    chk(name + ": пометки состояния — только четыре из легенды", used and not odd and all(m in t for m in marks), odd)
    body = t.split("## Outside the fifteen")[0] if "## Outside the fifteen" in t else t.split("## Вне пятнадцати")[0]
    each = [sec for sec in re.split(r"^## \d+\. ", body, flags=re.M)[1:]]
    chk(name + ": у каждого модуля есть хотя бы одна пометка состояния", len(each) == 15 and all(re.search(r"^- \*\*", sec, re.M) for sec in each))
en, ru = read("MODULES.md"), read("MODULES.ru.md")
chk("MODULES: в двух языках названы одни и те же пути, в том же порядке", [p for p in re.findall(r"`([^`\s]+)`", en) if "/" in p] == [p for p in re.findall(r"`([^`\s]+)`", ru) if "/" in p])
skills = lambda t: set(re.findall(r"`skills/([a-z0-9-]+)`", t))
chk("MODULES: навык не назван «в ядре» и «ждёт выпуска» одновременно", not (skills("".join(re.findall(r"^- \*\*in the core\*\*.*$", en, re.M))) & skills("".join(re.findall(r"^- \*\*accepted, awaits release\*\*.*$", en, re.M)))))
# the Mind page: the numbers it names are the numbers of the texts it points at
q = len(re.findall(r"^\| \d+ \|", open(os.path.join(REPO, "canon", "QUALITIES.md"), encoding="utf-8").read(), re.M))
laws = len(re.findall(r"^\d+\. ", open(os.path.join(REPO, "CONSTITUTION.md"), encoding="utf-8").read(), re.M))
chk("MIND: число качеств на странице — как в реестре (%d), число законов — как в конституции (%d)" % (q, laws),
    ("register of %d qualities" % q) in read("MIND.md") and ("реестр из %d качеств" % q) in read("MIND.ru.md") and laws == 10 and "Ten laws" in read("MIND.md") and "Десять законов" in read("MIND.ru.md"))
reg = open(os.path.join(REPO, "canon", "QUALITIES.md"), encoding="utf-8").read()
chk("MIND: четыре качества в таблице стоят в реестре под теми же именами", all(("**%s**" % x) in reg and x in read("MIND.ru.md") for x in ("Держу каждое дело", "Сделано с уликой", "Сама возвращаюсь", "Открыто и первой")))
chk("MIND: слова, которыми не говорим, названы как запрет, а не как утверждение", "We do not say she «feels»" in read("MIND.md") and "Не говорим: «чувствует»" in read("MIND.ru.md")
    and not re.search(r"she feels|Mila feels|is conscious", read("MIND.md"), re.I) and not re.search(r"Мила чувствует|она чувствует|осознаёт себя[^»]", read("MIND.ru.md")))
# a design page says in its first lines that nothing of it is in the core — and the map of modules marks the module the same way
pe, pr = read("design/PASSPORT.md"), read("design/PASSPORT.ru.md")
chk("design/PASSPORT: в первых строках — «в разработке, в ядре этого нет», на обоих языках", "**In development.** Nothing on this page is in the core yet" in "\n".join(pe.split("\n")[:6]) and "**В разработке.** Ничего из этой страницы в ядре пока нет" in "\n".join(pr.split("\n")[:6]))
sec = lambda t, head: t.split(head, 1)[1].split("\n## ", 1)[0]
chk("design/PASSPORT: карта модулей помечает Паспорт так же — «в разработке», и в ядре нет ни навыка, ни папки паспорта", "- **in development**" in sec(read("MODULES.md"), "## 2. Passport") and "- **в разработке**" in sec(read("MODULES.ru.md"), "## 2. Паспорт")
    and not any(os.path.exists(os.path.join(REPO, p)) for p in ("skills/passport", "skills/pasport", "passport")))
chk("design/PASSPORT: что решено и что открыто — названо таблицей, открытые решения помечены в тексте", "## What is decided and what is open" in pe and pe.count("*Open decision:*") == 2 and pr.count("*Открытое решение:*") == 2)
chk("design/PASSPORT: двенадцать слов — «Мила их не видит и не хранит» сказано прямо", "Mila never sees them and never keeps them" in pe and "Мила их не видит и не хранит" in pr)
# the index of the docs names every page — a new page that is not in the index is not found by a reader
for idx, twin in (("README.md", False), ("README.ru.md", True)):
    t = read(idx); listed = set(links(t))
    pages = sorted(os.path.relpath(os.path.join(r0, f), D) for r0, _, fs in os.walk(D) for f in fs if f.endswith(".md") and not f.startswith("README") and "exam-example" not in r0)
    want = [p for p in pages if not p.endswith(".ru.md")]
    if twin: want = [(p[:-3] + ".ru.md") if (p[:-3] + ".ru.md") in pages else p for p in want]
    miss = [p for p in want if p not in listed]
    chk(idx + ": в указателе названа каждая страница (%d)%s" % (len(want), ", русская — где она есть" if twin else ""), not miss, miss)
chk("указатель документации назван в каждом из четырёх README", all(("docs/README.ru.md" if f == "README.ru.md" else "docs/README.md") in open(os.path.join(REPO, f), encoding="utf-8").read()
    for f in ("README.md", "README.ru.md", "README.uz.md", "README.zh-CN.md")))
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
