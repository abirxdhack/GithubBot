import html as _html
import re

from helpers.buttons import SmartButtons


def esc(text) -> str:
    return _html.escape(str(text))


def repo_link(full_name: str) -> str:
    return f'<a href="https://github.com/{full_name}">{esc(full_name)}</a>'


def user_link(login: str) -> str:
    return f'<a href="https://github.com/{login}">{esc(login)}</a>'


def clean_body(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    lines = [esc(ln.strip()) for ln in text.split("\n") if ln.strip()]
    result = "\n".join(lines[:6])
    if len(result) > 500:
        result = result[:497] + "..."
    return result


def release_notes(raw: str) -> str:
    if not raw:
        return ""
    body = clean_body(raw)
    if not body:
        return ""
    lines = body.split("\n")
    if len(lines) <= 8:
        return "\n".join(f"<blockquote>{ln}</blockquote>" for ln in lines)
    top  = "\n".join(f"<blockquote>{ln}</blockquote>" for ln in lines[:5])
    rest = "\n".join(f"<blockquote>{ln}</blockquote>" for ln in lines[5:])
    return f"{top}\n<tg-spoiler>{rest}</tg-spoiler>"


def with_url_btn(text: str, label: str, url: str):
    if not label or not url:
        return text, None
    sb = SmartButtons()
    sb.button(label, url=url)
    return text, sb.build_menu(b_cols=1)


def action_icon(action: str) -> str:
    return {"created": "🆕", "edited": "✏️", "deleted": "🗑️"}.get(action, "🔹")
