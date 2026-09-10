"""오케스트레이터 테스트 — JSON 도구 호출 루프 + 컨텍스트 기록 + 규칙 폴백."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.classifier_adapter import ClassifierAdapter, MockClassifier
from agent.context import ConversationContext
from agent.harness import ToolHarness
from agent.orchestrator import Orchestrator
from agent.skills import default_skills
from agent.manager import ManagerAgent


def _make_harness():
    adapter = ClassifierAdapter()
    return ToolHarness(default_skills(adapter))


def test_llm_tool_call_runs_harness_and_returns():
    """LLM이 {'tool': 'get_tree'} 반환 → 하네스 실행 → 결과 포함 최종 응답."""
    harness = _make_harness()
    ctx = ConversationContext()

    def llm(prompt, **kw):
        return '{"tool": "get_tree", "arguments": {}}'

    orch = Orchestrator(harness, llm, context=ctx, max_steps=3)
    answer = orch.run("건 트리 알려줘")
    assert "N_CX" in answer or "이관" in answer
    assert ctx.steps_history(), "도구 실행 이력이 남아야 함"
    assert ctx.steps_history()[-1]["tool"] == "get_tree"


def test_llm_reply_stops_immediately():
    """LLM이 {'reply': ...} 반환 → 즉시 종료 (도구 호출 없음)."""
    harness = _make_harness()
    ctx = ConversationContext()

    def llm(prompt, **kw):
        return '{"reply": "안내문입니다."}'

    orch = Orchestrator(harness, llm, context=ctx, max_steps=3)
    assert orch.run("안녕") == "안내문입니다."
    assert not ctx.steps_history(), "도구 호출이 없어야 함"


def test_llm_error_falls_back_to_rules():
    """LLM이 오류(비JSON/예외) 반환 → 규칙 폴백으로도 응답."""
    harness = _make_harness()
    ctx = ConversationContext()

    def llm(prompt, **kw):
        raise RuntimeError("offline")

    orch = Orchestrator(harness, llm, context=ctx, max_steps=3)
    answer = orch.run("건 트리 알려줘")
    assert answer  # 빈 문자열이면 안 됨
    assert ctx.steps_history(), "폴백도 도구를 호출해 이력이 남아야 함"


def test_max_steps_force_stops():
    """LLM이 계속 도구만 호출 → max_steps 초과 시 강제 종료 (무한 루프 방지)."""
    harness = _make_harness()
    ctx = ConversationContext()

    def llm(prompt, **kw):
        return '{"tool": "answer_direct", "arguments": {"message": "계속"}}'

    orch = Orchestrator(harness, llm, context=ctx, max_steps=2)
    answer = orch.run("계속 도구 호출")
    assert isinstance(answer, str) and answer
    assert len(ctx.steps_history()) <= 2, "max_steps 초과 호출 금지"


def test_context_steps_are_recorded():
    """context.steps()에 도구 실행 기록이 남는다 (tool 이름 포함)."""
    harness = _make_harness()
    ctx = ConversationContext()

    def llm(prompt, **kw):
        return '{"tool": "get_case_emails", "arguments": {"case_id": "c-m0001"}}'

    orch = Orchestrator(harness, llm, context=ctx, max_steps=3)
    orch.run("c-m0001 타임라인 알려줘")
    tools = [s["tool"] for s in ctx.steps_history()]
    assert "get_case_emails" in tools


def test_manager_agent_still_works_with_orchestrator():
    """ManagerAgent가 오케스트레이터로 리팩터돼도 기존 사용법(메시지→문자열)이 동작."""
    agent = ManagerAgent(llm_call=lambda prompt, **kw: '{"tool": "get_tree", "arguments": {}}')
    answer = agent.run("건 트리 알려줘")
    assert "N_CX" in answer or "이관" in answer