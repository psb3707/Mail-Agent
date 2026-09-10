"""프롬프트 시스템 테스트 — 프롬프트 중앙화 모듈의 계약 확인."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.prompts import (
    FALLBACK_REPLY,
    JSON_FORMAT_GUIDE,
    SYSTEM_PROMPT,
    build_result_prompt,
    build_tool_prompt,
)


def test_system_prompt_is_korean_and_defines_role():
    """시스템 프롬프트가 한국어이며 역할 정의를 포함한다."""
    assert SYSTEM_PROMPT
    assert "메일 관리 Agent" in SYSTEM_PROMPT
    # 한국어 문장이 포함되어 있음을 확인 (일반적인 역할 서술 키워드)
    assert "사용자" in SYSTEM_PROMPT


def test_build_tool_prompt_includes_skills_and_format():
    """도구 선택 프롬프트에 스킬 이름·설명·JSON 형식 안내가 포함된다."""
    skills = [
        {"name": "tree", "description": "건 트리 조회"},
        {"name": "case_emails", "description": "건 메일 목록 조회"},
    ]
    history = [{"role": "user", "content": "건 트리 알려줘"}]
    prompt = build_tool_prompt(skills, history)
    assert "tree" in prompt
    assert "건 트리 조회" in prompt
    assert "case_emails" in prompt
    assert JSON_FORMAT_GUIDE in prompt
    assert "건 트리 알려줘" in prompt


def test_build_tool_prompt_handles_empty_history():
    """대화 이력이 없어도 조립이 동작한다."""
    prompt = build_tool_prompt([{"name": "tree", "description": "건 트리"}], [])
    assert "tree" in prompt


def test_build_result_prompt_includes_last_result():
    """결과 결정 프롬프트에 직전 결과가 포함된다."""
    prompt = build_result_prompt("분류된 건: A / B", [])
    assert "분류된 건: A / B" in prompt
    assert JSON_FORMAT_GUIDE in prompt


def test_fallback_reply_not_empty():
    """폴백 응답이 비어 있지 않다."""
    assert FALLBACK_REPLY.strip()
