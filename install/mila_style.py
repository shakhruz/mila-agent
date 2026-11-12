#!/usr/bin/env python3
"""The one look of every page Mila shows the owner while she is being born, signed in or given a key: the same family as the
birth page (cream paper, white rounded card, round portrait on top, serif teal heading, one teal button, small print, language pills).

Only stdlib, no outside requests: system fonts, the portrait is read from a file next to this module (or from the kit) and
inlined as a data: URI. No portrait on this machine - the page is the same without it.

This file is copied as is next to every page that uses it (install/, docker/, tools/seif/) the same way mila_i18n.py is; a test
keeps the copies identical.

  CSS                      the shared stylesheet (a string)
  face_uri()               "data:image/...;base64,..." or "" when no portrait is found
  shell(title, lg, body, lang_bar="", extra_css="", portrait=True)
                           a whole page as str: lang_bar sits above the card, body inside it under the portrait
  CSP                      Content-Security-Policy for these pages (images only from data:)"""
import base64, html, os

HERE = os.path.dirname(os.path.abspath(__file__))
CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; form-action 'self'"

CSS = """:root{color-scheme:light;--paper:#fbfbf8;--sand1:#f3e9db;--sand2:#e9d8bf;--sand:#d4a574;--ink:#134e4a;--mut:#41615d;--teal:#0f766e;--mint:#5eead4;--bad:#b42318;--gold:#8a5a1f}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:radial-gradient(900px 520px at 50% -8%,var(--sand1),var(--paper) 70%);color:var(--ink);font:17px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;flex-direction:column;align-items:center;padding:24px 16px 40px;overflow-x:hidden}
.card{width:100%;max-width:520px;background:#fff;border:1px solid var(--sand2);border-radius:26px;padding:28px 22px;text-align:center;box-shadow:0 10px 40px rgba(19,78,74,.08)}
.av{width:132px;height:132px;border-radius:50%;object-fit:cover;border:3px solid #fff;margin:2px auto 18px;display:block;box-shadow:0 0 0 8px rgba(233,216,191,.55),0 0 36px rgba(212,165,116,.35)}
h1,h2{font:600 28px/1.2 Georgia,serif;margin:0 0 10px;color:var(--ink);overflow-wrap:anywhere}h2{font-size:24px}
p{margin:0 0 16px;color:var(--mut);overflow-wrap:anywhere}
form{margin:0;text-align:left}label{display:block;margin:14px 0 6px;font-weight:600;font-size:15px;color:var(--ink)}
input{width:100%;font:16px ui-monospace,Menlo,monospace;padding:13px;border-radius:14px;border:1px solid var(--sand2);background:var(--paper);color:var(--ink);margin-top:6px}
input:focus{outline:2px solid var(--mint);border-color:var(--teal)}
input::placeholder{color:#8a9c99;font-size:14px}
button,a.btn,a.b{display:block;font-family:inherit;font-weight:600;font-size:17px;border:0;border-radius:14px;padding:14px 20px;cursor:pointer;width:100%;margin-top:16px;text-decoration:none;text-align:center;background:var(--teal);color:#fff}
button:hover,a.btn:hover,a.b:hover{background:#115e59}
.fine,small{font-size:14px;color:var(--mut)}.fine{margin:14px 0 0;text-align:center}
.e{color:var(--bad);font-size:15px;margin:10px 0 0}.ok{font-size:40px;text-align:center;line-height:1.2;margin-bottom:6px}
.lang{display:flex;gap:6px;margin:0 0 18px;flex-wrap:wrap;justify-content:center}
.lang a,.lang b{font-family:inherit;font-weight:600;font-size:13px;line-height:1.2;border-radius:999px;padding:6px 12px;background:#fff;color:var(--mut);border:1px solid var(--sand2);text-decoration:none}
.lang b{background:var(--teal);color:#fff;border-color:var(--teal)}
.center{text-align:center}"""


def face_uri():
    """The portrait as a data: URI. Looked up next to this file (the container and the safe ship the small one), then in the
    kit (install/birth-assets); nothing found - an empty string and the page simply has no portrait."""
    for name, mime in (("mila-face.webp", "image/webp"), ("birth-assets/portrait.jpg", "image/jpeg"),
                       (os.path.join("..", "install", "birth-assets", "portrait.jpg"), "image/jpeg"),
                       (os.path.join("..", "..", "install", "birth-assets", "portrait.jpg"), "image/jpeg")):
        try:
            with open(os.path.join(HERE, name), "rb") as f:
                return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode())
        except OSError:
            continue
    return ""


_FACE = None


def shell(title, lg, body, lang_bar="", extra_css="", portrait=True):
    global _FACE
    if _FACE is None:
        _FACE = face_uri()
    img = "<img class=av alt='' src='%s'>" % _FACE if portrait and _FACE else ""
    return ("<!doctype html><html lang=%s><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><meta name=referrer content=no-referrer><meta name=color-scheme content=light>"
            "<title>%s</title><style>%s%s</style></head><body>%s<div class=card>%s%s</div></body></html>"
            % (html.escape(lg, quote=True), html.escape(title), CSS, extra_css, lang_bar, img, body))
