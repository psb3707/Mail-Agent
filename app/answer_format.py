"""Render model Markdown with raw HTML and remote images disabled."""
from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table").disable("image")


def format_answer(result: dict) -> dict:
    """Keep plain answer for API clients and provide safe presentation HTML."""
    answer = result.get("answer") or "답변을 찾지 못했습니다."
    return {**result, "answer_html": _MARKDOWN.render(answer)}
