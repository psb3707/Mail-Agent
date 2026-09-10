from scripts.pm_review import is_sensitive_path, render_document, truncate


def test_sensitive_mailbox_data_is_excluded():
    assert is_sensitive_path("data/mails.json")
    assert is_sensitive_path("data/indexed.json")
    assert is_sensitive_path("data/attachments/a001.xlsx")
    assert is_sensitive_path(".env.production")
    assert not is_sensitive_path("app/search.py")
    assert not is_sensitive_path("docs/BACKLOG.md")


def test_truncate_preserves_short_text_and_marks_long_text():
    assert truncate("short", 10, "cut") == "short"
    result = truncate("abcdefghij", 4, "cut")
    assert result.startswith("abcd")
    assert "6 characters omitted" in result


def test_render_document_contains_review_metadata():
    document = render_document(
        repository="owner/repo",
        before="a" * 40,
        after="b" * 40,
        actor="reviewer",
        model="claude-sonnet-5",
        test_status="success",
        review="## 판정: GO\n\n검토 완료",
    )
    assert "owner/repo" in document
    assert "`" + "b" * 40 + "`" in document
    assert "## 판정: GO" in document

