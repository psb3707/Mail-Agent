"""Render model Markdown with raw HTML and remote images disabled."""
from markdown_it import MarkdownIt
from urllib.parse import quote, unquote

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table").disable("image")


def format_answer(result: dict, mails: dict | None = None) -> dict:
    """Keep plain answer for API clients and provide safe presentation HTML."""
    answer = result.get("answer") or "답변을 찾지 못했습니다."
    if mails is None:
        return {**result, "answer_html": _MARKDOWN.render(answer)}
    ids = list(result.get("mail_ids") or [])
    ids += [s.get("id") for s in result.get("sources", []) if isinstance(s, dict)]
    sources = []
    for mid in dict.fromkeys(mid for mid in ids if isinstance(mid, str)):
        if mid not in mails:
            continue
        m = mails[mid]
        sources.append({"id": mid, "subject": m.get("subject", ""),
                        "sender": m.get("sender_name", ""), "date": m.get("sent_at", "")[:10],
                        "excerpt": m.get("body", "")[:240], "url": "/#mail-" + quote(mid, safe="")})
    tokens = _MARKDOWN.parse(answer)
    for block in tokens:
        for token in block.children or []:
            if token.type == "link_open":
                href = token.attrGet("href") or ""
                if href.startswith(("/#mail-", "#mail-")):
                    mid = unquote(href.split("#mail-", 1)[1])
                    if mid not in mails:
                        token.attrs.pop("href", None)
    return {**result, "sources": sources, "answer_html": _MARKDOWN.renderer.render(tokens, _MARKDOWN.options, {})}
