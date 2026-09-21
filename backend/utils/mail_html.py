from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


_BLOCKED = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "svg"}
_ALLOWED = {
    "p", "div", "br", "hr", "strong", "b", "em", "i", "u",
    "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "a", "img",
}


def _safe_url(value: str | None, *, image: bool = False) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if image:
        return raw if parsed.scheme == "https" and bool(parsed.netloc) else None
    if parsed.scheme in {"https", "http", "mailto"}:
        return raw
    return None


_STYLE = {
    "p": "margin:0 0 16px;line-height:1.65;color:#182033;font-size:16px;",
    "div": "margin:0 0 16px;line-height:1.65;color:#182033;font-size:16px;",
    "h1": "margin:0 0 18px;font-size:30px;line-height:1.2;color:#111827;",
    "h2": "margin:0 0 16px;font-size:24px;line-height:1.25;color:#111827;",
    "h3": "margin:0 0 14px;font-size:19px;line-height:1.3;color:#111827;",
    "ul": "margin:0 0 16px;padding-left:24px;color:#182033;font-size:16px;line-height:1.6;",
    "ol": "margin:0 0 16px;padding-left:24px;color:#182033;font-size:16px;line-height:1.6;",
    "li": "margin:0 0 8px;",
    "blockquote": "margin:0 0 16px;padding:12px 16px;border-left:4px solid #6857ff;background:#f5f3ff;color:#4b5563;",
    "hr": "border:0;border-top:1px solid #e5e7eb;margin:24px 0;",
    "a": "color:#5b4df7;text-decoration:underline;",
    "img": "display:block;max-width:100%;height:auto;border:0;border-radius:12px;margin:18px auto;",
}
_BUTTON_STYLE = (
    "display:inline-block;padding:12px 20px;border-radius:10px;"
    "background:#6557ff;color:#ffffff;text-decoration:none;font-weight:700;"
)


class _MailHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.stack: list[str] = []
        self.blocked_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _BLOCKED:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in _ALLOWED:
            return

        normalized = {"b": "strong", "i": "em"}.get(tag, tag)
        values = {str(key).lower(): str(value or "") for key, value in attrs}

        if normalized == "img":
            src = _safe_url(values.get("src"), image=True)
            if not src:
                return
            alt = escape(values.get("alt", ""), quote=True)
            title = escape(values.get("title", ""), quote=True)
            title_attr = f' title="{title}"' if title else ""
            self.output.append(
                f'<img src="{escape(src, quote=True)}" alt="{alt}"{title_attr} style="{_STYLE["img"]}">'
            )
            return

        if normalized == "br":
            self.output.append("<br>")
            return
        if normalized == "hr":
            self.output.append(f'<hr style="{_STYLE["hr"]}">')
            return

        attr_text = ""
        if normalized == "a":
            href = _safe_url(values.get("href"))
            if not href:
                normalized = "span"
            else:
                is_button = values.get("data-mail-button") == "1"
                style = _BUTTON_STYLE if is_button else _STYLE["a"]
                attr_text = (
                    f' href="{escape(href, quote=True)}"'
                    f' style="{style}" target="_blank" rel="noopener noreferrer"'
                )

        if normalized in _STYLE and normalized != "a":
            attr_text += f' style="{_STYLE[normalized]}"'

        self.output.append(f"<{normalized}{attr_text}>")
        self.stack.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _BLOCKED:
            if self.blocked_depth:
                self.blocked_depth -= 1
            return
        if self.blocked_depth:
            return
        normalized = {"b": "strong", "i": "em"}.get(tag, tag)
        if normalized in {"img", "br", "hr"}:
            return
        if normalized not in self.stack:
            return
        while self.stack:
            opened = self.stack.pop()
            self.output.append(f"</{opened}>")
            if opened == normalized:
                break

    def handle_data(self, data: str) -> None:
        if not self.blocked_depth:
            self.output.append(escape(data))

    def close_all(self) -> None:
        while self.stack:
            self.output.append(f"</{self.stack.pop()}>")


class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "div", "h1", "h2", "h3", "li", "blockquote", "br", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.BLOCKS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            punctuation = ".,!?;:)]}…"
            if (
                self.parts
                and not self.parts[-1].endswith(("\n", " ", "(", "[", "{"))
                and not text.startswith(tuple(punctuation))
            ):
                self.parts.append(" ")
            self.parts.append(text)


def sanitize_mail_html(value: str | None) -> str:
    parser = _MailHTMLSanitizer()
    parser.feed(str(value or ""))
    parser.close()
    parser.close_all()
    return "".join(parser.output).strip()


def html_to_text(value: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(str(value or ""))
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n\n".join(line for line in lines if line).strip()


def render_mail_document(fragment: str) -> str:
    safe_fragment = sanitize_mail_html(fragment)
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f5f6fb;'
        'font-family:Arial,sans-serif;color:#182033;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="width:100%;background:#f5f6fb;padding:28px 12px;"><tr><td align="center">'
        '<table role="presentation" width="640" cellspacing="0" cellpadding="0" '
        'style="width:100%;max-width:640px;background:#ffffff;border-radius:16px;'
        'box-shadow:0 8px 32px rgba(15,23,42,.08);"><tr><td style="padding:32px;">'
        + safe_fragment
        + '</td></tr></table></td></tr></table></body></html>'
    )
