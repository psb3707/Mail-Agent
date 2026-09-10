"""관리 Agent 골격 스모크 테스트 — 분류AI 구현 없이 목으로 동작 확인."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.classifier_adapter import ClassifierAdapter, MockClassifier
from agent.context import ConversationContext
from agent.manager import ManagerAgent
from agent.responder import render_tool_result


def test_mock_classifier_adapter_serves_tree():
    """분류AI 본체가 없어도(목) 트리 조회가 동작한다."""
    adapter = ClassifierAdapter()  # impl 미지정 → MockClassifier
    tree = adapter.get_tree()
    assert tree["root"] == "메일함"
    assert any(c["title"] for c in tree["cases"])


def test_mock_adapter_case_emails_and_attachment():
    """목 어댑터가 건 메일 목록·첨부 텍스트를 반환한다."""
    adapter = ClassifierAdapter()
    emails = adapter.get_case_emails("c-m0001")
    assert emails and emails[0]["subject"]
    assert adapter.get_attachment_text("a001")  # 비어 있지 않음


def test_manager_agent_tree_intent():
    """'건' 키워드 → tree 도구 → 응답에 분류 건이 포함."""
    agent = ManagerAgent()
    answer = agent.run("지금 분류된 건 트리 알려줘")
    assert "N_CX" in answer or "이관" in answer


def test_manager_agent_timeline_intent():
    """'타임라인' 키워드 + case id → 건 타임라인 응답."""
    agent = ManagerAgent()
    answer = agent.run("c-m0001 타임라인 알려줘")
    assert "m0001" in answer or "N_CX" in answer


def test_manager_agent_attachment_intent():
    """'첨부 내용' 키워드 + 첨부 id → 첨부 텍스트 응답."""
    agent = ManagerAgent()
    answer = agent.run("a001 첨부 내용 알려줘")
    assert "견적" in answer


def test_conversation_context_tracks_turns():
    """대화 맥락이 user/agent 턴을 인메모리로 유지한다."""
    ctx = ConversationContext(max_turns=3)
    ctx.add_user("안녕")
    ctx.add_agent("네, 무엇을 도와드릴까요?")
    ctx.add_user("견적 알려줘")
    assert len(ctx.history()) == 3
    assert ctx.last_user_message() == "견적 알려줘"


def test_manager_agent_with_llm_pick_tool_uses_llm():
    """LLM 스텁이 JSON 도구 호출을 반환하면 그 도구를 따른다 (라이브 기본 원칙).

    지시-010 리팩터: LLM은 도구 이름 대신 JSON 규약
    `{"tool": "...", "arguments": {...}}`을 반환해야 한다.
    """
    agent = ManagerAgent(
        llm_call=lambda prompt, **kw: '{"tool": "get_attachment_text", "arguments": {"attachment_id": "a001"}}'
    )
    answer = agent.run("아무 말이나 해")
    assert "첨부" in answer  # LLM이 get_attachment_text 선택


def test_render_tool_result_shapes():
    """응답 생성기가 도구 결과를 텍스트로 만든다."""
    assert "N_CX" in render_tool_result("tree", {"cases": [{"title": "N_CX 건"}]})
    assert "타임라인" in render_tool_result("case_emails", [{"sent_at": "2026-05-04", "subject": "안내"}])
    assert "첨부" in render_tool_result("attachment_text", "본문 내용")