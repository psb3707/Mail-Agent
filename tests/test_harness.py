"""스킬/도구 하네스 테스트 — 등록·목록·실행·어댑터 교체 (지시 009)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.classifier_adapter import ClassifierAdapter
from agent.harness import ToolHarness
from agent.skills import Skill, default_skills


def _harness() -> ToolHarness:
    """Mock 분류AI 어댑터로 기본 스킬 4개를 등록한 하네스."""
    clf = ClassifierAdapter()  # 미지정 → MockClassifier
    return ToolHarness(default_skills(clf))


def test_default_skills_registered():
    """기본 스킬 4개(get_tree·get_case_emails·get_attachment_text·answer_direct) 등록."""
    h = _harness()
    names = [s["name"] for s in h.list_skills()]
    assert set(names) >= {
        "get_tree",
        "get_case_emails",
        "get_attachment_text",
        "answer_direct",
    }
    # 설명이 한글(LLM이 읽을 용도)로 비어 있지 않음
    assert all(s["description"] for s in h.list_skills())


def test_execute_get_tree_returns_dict():
    """execute('get_tree') → MockClassifier의 트리 dict 반환."""
    h = _harness()
    result = h.execute("get_tree")
    assert isinstance(result, dict)
    assert "cases" in result


def test_execute_get_case_emails_with_arg():
    """execute('get_case_emails', {case_id}) → list 반환."""
    h = _harness()
    result = h.execute("get_case_emails", {"case_id": "c-m0001"})
    assert isinstance(result, list)
    assert result and result[0]["subject"]


def test_execute_get_attachment_text_with_arg():
    """execute('get_attachment_text', {attachment_id}) → str 반환."""
    h = _harness()
    result = h.execute("get_attachment_text", {"attachment_id": "a001"})
    assert isinstance(result, str) and result


def test_execute_unknown_skill_raises():
    """없는 스킬 호출 시 KeyError를 일으킨다."""
    h = _harness()
    try:
        h.execute("no_such_tool", {})
    except KeyError:
        pass
    else:
        raise AssertionError("없는 스킬은 KeyError여야 한다")


def test_execute_reply_direct():
    """answer_direct는 안내 응답을 문자열로 반환."""
    h = _harness()
    result = h.execute("answer_direct", {"message": "안녕하세요"})
    assert isinstance(result, str) and result


def test_set_classifier_replaces_skills():
    """set_classifier로 어댑터를 교체하면 새 어댑터로 스킬이 다시 등록된다."""
    class FakeImpl:
        def get_tree(self):
            return {"root": "메일함", "cases": [{"id": "c-new", "title": "새 건"}]}

        def get_case_emails(self, case_id):
            return [{"subject": "새 메일", "sent_at": "2026-09-10"}]

        def get_attachment_text(self, attachment_id):
            return "새 첨부 본문"

    h = _harness()
    h.set_classifier(FakeImpl())
    result = h.execute("get_tree")
    assert result["cases"][0]["id"] == "c-new"  # 새 어댑터 결과


def test_custom_skill_registration():
    """사용자 정의 스킬을 등록하고 실행할 수 있다."""
    h = _harness()
    h.register(
        Skill(
            name="custom_echo",
            description="입력 메시지를 그대로 돌려준다.",
            handler=lambda args: args.get("message", ""),
            parameters={"type": "object", "properties": {"message": {"type": "string"}}},
        )
    )
    assert h.execute("custom_echo", {"message": "hello"}) == "hello"