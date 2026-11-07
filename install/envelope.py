#!/usr/bin/env python3
"""The `<channel source="telegram" …>` envelope the session reads — one builder for the feeder (Mila Agent) and the
UserPromptSubmit hook (a plain install), so both carry the same attributes and the same escaping.

Attributes: chat_id, message_id, user, lang, ts, and what the receiver knows about the message — user_id, from
(owner/team/other), type (reaction/callback), observe_only, chat_type, guests_since_last, chat_title. Only known values
(patterns) go into attributes; everything from the chat is escaped, so a crafted name or text cannot close the envelope or
fake an attribute."""
import re

ATTRS = (("user_id", r"[0-9]{1,15}"), ("from", r"owner|team|other"), ("type", r"reaction|callback"), ("observe_only", r"true"),
         ("chat_type", r"private|group|supergroup|channel"), ("guests_since_last", r"[0-9]{1,6}"),
         ("flags", r"(hidden-chars|instruction-like)(,(hidden-chars|instruction-like))?"))   # the receiver marked the text: data, not an order
LANG = r"[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})?"


def esc(v):
    """everything that came from a chat is data, not markup"""
    return (str("" if v is None else v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def meta_attrs(m):
    out = "".join(' %s="%s"' % (k, m[k]) for k, pat in ATTRS if re.fullmatch(pat, str(m.get(k) or "")))
    if m.get("chat_title"):
        out += ' chat_title="%s"' % esc(str(m["chat_title"])[:128])
    return out


def envelope(p, m, quote_max=3000):
    """p — the event's params (content), m — its meta."""
    who = m.get("user") or "id:%s" % m.get("user_id", "?")
    txt = (p.get("content") or "").strip()
    att = ""
    if m.get("image_path"):
        att = " [image: %s]" % m["image_path"]
    elif m.get("attachment_file_id"):
        att = " [attachment_file_id: %s]" % m["attachment_file_id"]
    quote = " (replying to: %s)" % esc(str(m["reply_quote"])[:quote_max]) if m.get("reply_quote") else ""
    lang = m.get("lang") if re.fullmatch(LANG, str(m.get("lang") or "")) else ""
    return ('<channel source="telegram" chat_id="%s" message_id="%s" user="%s"%s ts="%s"%s>%s%s%s</channel>'
            % (esc(m.get("chat_id")), esc(m.get("message_id")), esc(who), (' lang="%s"' % lang) if lang else "", esc(m.get("ts", "")),
               meta_attrs(m), esc(txt), esc(att), quote))
