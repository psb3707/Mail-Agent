"""지시-013 통합 검증 — 009(하네스)·010(오케스트레이터)·011(프롬프트)가
하나의 ManagerAgent로 맞물려 실제 응답까지 동작하는지 확인한다.

- Mock 분류AI(ClassifierAdapter 기본값) 상태에서 스모크 동작
- 도구 실행 경로(하네스)와 컨텍스트 기록이 실제로 연결되는지 확인
- 라이브 LLM 기본(스텁 JSON → 도구 실행) 경로 확인
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent
from agent import ManagerAgent
from agent.classifier_adapter import ClassifierAdapter
from agent.context import ConversationContext
from agent.skills import default_skills


def test_manager_agent_is_exported_from_package():
    """agent/__init__.py가 ManagerAgent를 노출한다 (009~011 + 010 리팩터 로드 확인)."""
    assert hasattr(agent, "ManagerAgent")
    assert agent.ManagerAgent is ManagerAgent


def test_manager_agent_smoke_returns_string():
    """Mock 분류AI 상태에서 run('안녕') → 문자열 응답 (스모크, 조건 2)."""
    agent_inst = ManagerAgent()
    reply = agent_inst.run("안녕")
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_manager_agent_harness_and_context_are_wired():
    """하네스에 기본 스킬 4개가 등록되고 컨텍스트가 대화를 기록한다 (조건 4)."""
    agent_inst = ManagerAgent()
    skills = agent_inst.harness.list_skills()
    names = {s["name"] for s in skills}
    assert {"get_tree", "get_case_emails", "get_attachment_text", "answer_direct"} <= names

    reply = agent_inst.run("건 트리 좀 보여줘")
    assert agent_inst.context.last_user_message() == "건 트리 좀 보여줘"
    assert isinstance(reply, str) and len(reply) > 0


def test_manager_agent_tool_execution_path_returns_tree():
    """규칙 폴백으로 '건' → get_tree 도구가 실행되어 분류 건이 응답에 포함된다."""
    agent_inst = ManagerAgent()
    reply = agent_inst.run("지금 분류된 건 트리를 알려주세요")
    assert "N_CX" in reply or "이관" in reply


def test_manager_agent_llm_json_tool_call_runs_harness():
    """LLM 스텁이 JSON 도구 호출을 반환하면 하네스를 통해 실제 도구가 실행된다."""
    agent_inst = ManagerAgent(
        llm_call=lambda prompt, **kw: (
            '{"tool": "get_case_emails", "arguments": {"case_id": "c-m0001"}}'
        )
    )
    reply = agent_inst.run("c-m0001 타임라인 좀 봐줘")
    # 하네스가 mock 분류AI의 get_case_emails를 실행 → m0001·m0006 포함 응답
    assert "m0001" in reply or "N_CX" in reply
    assert len(agent_inst.context.steps_history()) >= 1


def test_manager_agent_conversation_continuity():
    """같은 에이전트 인스턴스에서 대화 맥락이 유지되어 레이턴시 없이 이어간다."""
    agent_inst = ManagerAgent()
    first = agent_inst.run("안녕하세요")
    assert isinstance(first, str)
    second = agent_inst.run("아까 그 트리 다시 보여줘")
    assert isinstance(second, str)
    # 두 턴 모두 컨텍스트에 기록
    assert len(agent_inst.context.history()) >= 4  # user,agent × 2