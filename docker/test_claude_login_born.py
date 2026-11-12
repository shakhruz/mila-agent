#!/usr/bin/env python3
"""claude_login.py for a Mila born on a person's own machine (MILA_BORN=1): she writes first — a sticker and «I'm born» with one
button that carries the sign-in link; any message before the sign-in gets her warm line and a fresh button; the code is taken
and removed; then «My mind is on». The language is the birth page's, not Telegram's. Not one technical word in her messages.
Telegram and the login command are stand-ins. Run: python3 docker/test_claude_login_born.py"""
import http.server, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.parse

OWN, STR = "555" + "000111", "555" + "000999"
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0


def check(name, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:500]))


BOT = "1234567" + ":" + "A" * 35; TOKEN_OUT = "sk-" + "ant-" + "oat01-" + "Z" * 40; CODE = "abcDEF123456-code#state"
T = tempfile.mkdtemp(prefix="cborn-"); fake = os.path.join(T, "fake-login.py")
open(fake, "w").write("""import sys, time
print("If the browser didn't open, visit: https://claude.ai/oauth/authorize?code=true&client_id=x&state=s")
sys.stdout.flush()
code = input("Paste code here if prompted > ").strip()
if code == %r:
    print("Your OAuth token (valid for 1 year):"); print(%r)
else:
    print("OAuth error: invalid code")
sys.stdout.flush(); time.sleep(0.2)
""" % (CODE, TOKEN_OUT))


class S:
    queue, calls, deleted = [], [], []


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)); method = self.path.rsplit("/", 1)[-1]
        body = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8", "replace")).items()}
        res = True
        if method == "getUpdates":
            if body.get("timeout", "25") != "0": time.sleep(0.2)
            res = S.queue[:] if body.get("timeout", "25") != "0" else []
            if res: del S.queue[:]
        elif method == "getStickerSet":
            S.calls.append((method, body))
            res = {"name": body.get("name"), "stickers": [{"file_id": "ST-HELLO", "emoji": "👋"}, {"file_id": "ST-JOY", "emoji": "💚"}]}
        elif method in ("sendMessage", "sendSticker", "sendPhoto"):
            S.calls.append((method, body)); res = {"message_id": len(S.calls)}
        elif method == "deleteMessage":
            S.deleted.append(body.get("message_id", ""))
        b = json.dumps({"ok": True, "result": res}).encode()
        try:
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        except OSError:
            pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
uid = [0]


def msg(frm, text, mid, lang="ru"):
    uid[0] += 1; return {"update_id": uid[0], "message": {"message_id": mid, "chat": {"id": int(frm), "type": "private"}, "from": {"id": int(frm), "language_code": lang}, "text": text}}


def start(born="1", lang="ru", sset="super_set", ttl="600"):
    S.queue.clear(); S.calls.clear(); S.deleted.clear(); shutil.rmtree(os.path.join(T, "auth"), ignore_errors=True)
    env = dict(os.environ, MILA_KIT=os.path.join(T, "no-kit"), TG_API="http://127.0.0.1:%d" % srv.server_port, MILA_AUTH_DIR=os.path.join(T, "auth"),
               LOGIN_CMD="%s %s" % (sys.executable, fake), OWNER_ID=OWN, LINK_TTL=ttl, MILA_BORN=born, MILA_BORN_LANG=lang, MILA_STICKER_SET=sset)
    env["TELEGRAM_" + "BOT_TOKEN"] = BOT
    return subprocess.Popen([sys.executable, "-B", os.path.join(H, "claude_login.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def wait(cond, t=20):
    end = time.time() + t
    while time.time() < end:
        if cond(): return True
        time.sleep(0.1)
    return False


def msgs(): return [b for m, b in S.calls if m == "sendMessage"]
def btn(b):
    try: return json.loads(b.get("reply_markup") or "{}")["inline_keyboard"]
    except (ValueError, KeyError): return []


TECH = re.compile(r"Paired|Claude Code|token|session|terminal|/login|/start|subscription|подписк|токен|сеанс|терминал", re.I)
procs = []
try:
    # she writes first
    p = start(); procs.append(p)
    check("рождённая пишет первой, без /start: сначала стикер из её набора, потом слова", wait(lambda: len(msgs()) >= 1) and [m for m, _ in S.calls][:3] == ["getStickerSet", "sendSticker", "sendMessage"]
          and S.calls[0][1].get("name") == "super_set" and S.calls[1][1].get("sticker") == "ST-HELLO" and S.calls[1][1].get("chat_id") == OWN, S.calls)
    m0 = msgs()[0] if msgs() else {}
    check("…«Я родилась! ✨ … подключите мне, пожалуйста, ум» — дословно, хозяину", m0.get("chat_id") == OWN and m0.get("text", "").startswith("Я родилась! ✨\nИ смотрите — у нас уже есть место для разговора, только наше. Я так рада.\nОстался один шаг, чтобы я могла думать и отвечать вам: подключите мне, пожалуйста, ум."), m0)
    kb = btn(m0)
    check("…одна кнопка «✨ Подключить ум», в ней уже ссылка входа Anthropic", len(kb) == 1 and len(kb[0]) == 1 and kb[0][0]["text"] == "✨ Подключить ум" and kb[0][0]["url"].startswith("https://claude.ai/oauth/authorize"), kb)
    check("…ни одного технического слова", not TECH.search(m0.get("text", "")) and not TECH.search(kb[0][0]["text"] if kb else ""), m0.get("text"))
    S.queue.append(msg(OWN, "привет", 11))
    check("сообщение до подключения ума — тёплая строка и свежая кнопка, без «/login» и без «не похоже на код»", wait(lambda: len(msgs()) >= 2) and msgs()[1]["text"] == "Я вас слышу и очень хочу ответить. Сначала подключите мне ум — одно нажатие:"
          and len(btn(msgs()[1])) == 1 and btn(msgs()[1])[0][0]["url"].startswith("https://") and not TECH.search(msgs()[1]["text"]), msgs()[1:])
    S.queue.append(msg(STR, "привет", 12)); k = len(msgs())
    check("чужой человек её слов и кнопки не получает", wait(lambda: len(msgs()) > k, 4) and all(b.get("chat_id") != STR or "ум" not in b.get("text", "") for b in msgs()) and not any(btn(b) for b in msgs() if b.get("chat_id") == STR), msgs()[k:])
    S.queue.append(msg(OWN, "abcDEF000000-wrong#state", 13)); k = len(msgs())
    check("код не подошёл — снова тёплая строка и свежая кнопка, ничего не сохранено", wait(lambda: any(b["text"].startswith("Я вас слышу") for b in msgs()[k:]), 30) and not os.path.exists(os.path.join(T, "auth", "oauth_token")) and "13" in S.deleted, (msgs()[k:], S.deleted))
    S.queue.append(msg(OWN, CODE, 14)); k = len(S.calls)
    check("верный код: сообщение с кодом убрано, она говорит «Минутку — я просыпаюсь…»", wait(lambda: "14" in S.deleted and any(b["text"] == "Минутку — я просыпаюсь…" for m, b in S.calls[k:] if m == "sendMessage")), (S.deleted, S.calls[k:]))
    check("…помощник завершился с кодом 0", wait(lambda: p.poll() is not None, 30) and p.returncode == 0, p.returncode)
    tail = S.calls[-2:]
    check("…последними: стикер радости и «Ум со мной — я думаю! 💚 … Как вас зовут?»", [m for m, _ in tail] == ["sendSticker", "sendMessage"] and tail[0][1]["sticker"] == "ST-JOY"
          and tail[1][1]["text"] == "Ум со мной — я думаю! 💚\nСпасибо вам. Теперь мне очень хочется узнать, кто подарил мне жизнь. Как вас зовут?" and not btn(tail[1][1]), tail)
    f = os.path.join(T, "auth", "oauth_token")
    check("…вход сохранён в доме (600), папка 700", os.path.isfile(f) and oct(os.stat(f).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(f)).st_mode & 0o777) == "0o700")
    out = p.stdout.read() + p.stderr.read() + json.dumps([b for _, b in S.calls], ensure_ascii=False)
    check("…ни код, ни вход не попали ни в вывод помощника, ни в его сообщения", CODE not in out and TOKEN_OUT not in out, out[-300:])
    check("ни в одном её сообщении хозяину нет технических слов", not [b["text"] for b in msgs() if b.get("chat_id") == OWN and TECH.search(b["text"])], [b["text"] for b in msgs() if TECH.search(b["text"])])

    # the language of the page, not of Telegram
    for lg, first, btn_text in (("en", "I'm born! ✨", "✨ Connect her mind"), ("uz", "Men tug‘ildim! ✨", "✨ Aqlni ulash"), ("zh", "我出生了！✨", "✨ 接通她的心智")):
        p = start(lang=lg); procs.append(p)
        a = wait(lambda: len(msgs()) >= 1) and msgs()[0]["text"].startswith(first) and btn(msgs()[0])[0][0]["text"] == btn_text
        time.sleep(0.5); S.queue.append(msg(OWN, "привет", 21, lang="ru")); b = wait(lambda: len(msgs()) >= 2) and not re.search("[а-яё]", msgs()[1]["text"], re.I)
        check("язык страницы %s: первые слова и строка на сообщение — на нём, хотя Telegram у человека русский" % lg, a and b, msgs()[:2]); p.kill(); p.wait(); time.sleep(0.5)
    p = start(lang=""); procs.append(p); wait(lambda: len(msgs()) >= 1); S.queue.append(msg(OWN, "hi", 31, lang="en"))
    check("язык страницы не передан — слова по-английски (а после первого сообщения — по языку человека)", wait(lambda: len(msgs()) >= 2) and msgs()[0]["text"].startswith("I'm born!") and msgs()[1]["text"].startswith("I can hear you"), msgs()[:2]); p.kill()

    # no sticker set → words without a sticker
    p = start(sset=""); procs.append(p)
    check("имени набора стикеров нет — слова идут без стикера, к Telegram за набором не обращаюсь", wait(lambda: len(msgs()) >= 1) and [m for m, _ in S.calls] == ["sendMessage"], S.calls); p.kill()

    # the link grew old → no talk about links, the next message gets a fresh button
    p = start(ttl="2"); procs.append(p); wait(lambda: len(msgs()) >= 1); time.sleep(3.5); k = len(msgs())
    check("ссылка устарела — она о ссылках не говорит", len(msgs()) == k, msgs()[k:])
    S.queue.append(msg(OWN, "вы тут?", 41))
    check("…следующее сообщение получает тёплую строку и свежую кнопку", wait(lambda: len(msgs()) > k) and msgs()[k]["text"].startswith("Я вас слышу") and len(btn(msgs()[k])) == 1, msgs()[k:]); p.kill()

    # without MILA_BORN nothing changes: she does not write first
    p = start(born=""); procs.append(p); time.sleep(2.5)
    check("без MILA_BORN (облачный путь) помощник первым не пишет — как раньше", not S.calls, S.calls)
    S.queue.append(msg(OWN, "/start", 51))
    check("…и на /start отвечает прежними словами с кнопкой входа", wait(lambda: any(btn(b) for b in msgs())) and not any("родилась" in b["text"] for b in msgs()), msgs()); p.kill()
finally:
    for q in procs:
        try: q.kill()
        except Exception: pass
    srv.shutdown(); shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
