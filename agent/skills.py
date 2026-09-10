"""스킬(도구) 정의 — 관리 Agent가 사용할 도구의 데이터 모델과 기본 스킬 목록.

도구는 하드코딩이 아니라 **데이터로 등록·관리**한다. 오케스트레이터(지시-010)가
이 스킬 목록을 LLM에 던져 도구를 선택하게 한다.

원칙:
- 스킬은 순수 실행 (부작용 없음, 인메모리) — DB 없음
- 분류AI 연동은 어댑터(`classifier_adapter.py`)가 담당하며, 스킬은 그 API를 그대로 호출한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# handler 시그니처: 인자 dict를 받아 실행 결과(Any)를 반환
SkillHandler = Callable[[dict[str, Any]], Any]


@dataclass
class Skill:
    """관리 Agent가 호출할 수 있는 도구 하나.

    - name: LLM이 JSON으로 호출할 때 쓰는 이름 (예: "get_case_emails")
    - description: LLM이 도구 선택 시 읽는 **한글 설명** (언제 쓰는지 명확히)
    - parameters: JSON Schema 형태의 인자 정의 (dict) — 없으면 {}
    - handler: 인자 dict → 결과를 실행하는 Callable
    """

    name: str
    description: str
    handler: SkillHandler
    parameters: dict[str, Any] = field(default_factory=dict)

    def execute(self, arguments: dict[str, Any] | None = None) -> Any:
        """인자 dict로 handler를 호출한다. 인자 없으면 {}로 호출."""
        return self.handler(arguments or {})


def default_skills(classifier) -> list[Skill]:
    """분류AI 어댑터(classifier)에 연결된 기본 스킬 4개를 만든다.

    - get_tree            : 건 트리 전체 조회
    - get_case_emails     : 지정한 건(case_id)의 메일 타임라인 조회
    - get_attachment_text : 지정한 첨부(attachment_id)의 추출 텍스트 조회
    - answer_direct       : 도구 조회 없이 바로 답할 때 (안내 문구)
    """
    return [
        Skill(
            name="get_tree",
            description=(
                "메일함 전체를 건(件) 단위로 분류한 트리를 조회한다. "
                "'지금 어떤 건이 있지?', '메일함 정리 상태 알려줘' 같은 질문에 쓴다. "
                "인자 없음."
            ),
            handler=lambda args: classifier.get_tree(),
            parameters={},
        ),
        Skill(
            name="get_case_emails",
            description=(
                "특정 건(case)에 속한 메일 목록(타임라인)을 조회한다. "
                "'c-m0001 건의 메일들 알려줘', '그 건 타임라인 봐줘' 같은 요청에 쓴다. "
                "인자: case_id (필수, 예: 'c-m0001')."
            ),
            handler=lambda args: classifier.get_case_emails(args["case_id"]),
            parameters={
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "string",
                        "description": "조회할 건의 id (예: 'c-m0001').",
                    }
                },
                "required": ["case_id"],
            },
        ),
        Skill(
            name="get_attachment_text",
            description=(
                "특정 첨부 파일의 추출된 전문(텍스트)을 조회한다. "
                "'a001 첨부 내용 알려줘', '견적서 본문 봐줘' 같은 요청에 쓴다. "
                "인자: attachment_id (필수, 예: 'a001')."
            ),
            handler=lambda args: classifier.get_attachment_text(args["attachment_id"]),
            parameters={
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "조회할 첨부의 id (예: 'a001').",
                    }
                },
                "required": ["attachment_id"],
            },
        ),
        Skill(
            name="answer_direct",
            description=(
                "도구 조회 없이 바로 답변할 수 있을 때 사용한다. "
                "일반 인사·안내·도움말 요청에 쓴다. "
                "인자: message (필수, 사용자 메시지 원문)."
            ),
            handler=lambda args: (
                "메일 속 필요한 내용을 함께 찾아볼게요. 최근 메일 요약이나 "
                "최종 견적, 업무 진행 상황을 편하게 물어보세요."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "답변할 사용자 메시지 원문.",
                    }
                },
                "required": ["message"],
            },
        ),
    ]


def mailbox_skills(indexed: dict, llm_call) -> list[Skill]:
    """Production tools use the real read-only mailbox, never mock records."""
    from app import search, grouping
    mails = grouping._mails_from(indexed)

    def schema(name, description):
        return {"type": "object", "properties": {name: {"type": "string", "description": description}},
                "required": [name], "additionalProperties": False}

    def tree(_):
        return {"cases": [{"id": c["id"], "title": c["title"],
                           "mail_count": len(c.get("mail_ids", [])),
                           "attachment_ids": c.get("attachment_ids", [])}
                          for c in indexed.get("cases", [])]}

    def case_emails(args):
        case = next((c for c in indexed.get("cases", []) if c["id"] == args["case_id"]), None)
        if case is None:
            raise ValueError("해당 업무를 찾을 수 없습니다. get_tree에서 실제 ID를 확인하세요.")
        return sorted([mails[mid] for mid in case["mail_ids"] if mid in mails], key=lambda m: m.get("sent_at", ""))

    def attachment(args):
        aid = args["attachment_id"]
        if aid not in indexed.get("attachment_texts", {}):
            raise ValueError("해당 첨부를 찾을 수 없습니다. 조회 결과의 ID를 사용하세요.")
        return indexed["attachment_texts"][aid]

    return [
        Skill("search_documents", "특정 업무의 견적, 금액, 일정, 첨부 문서 질문에 답하고 검증 근거를 반환합니다. 원래 질문을 그대로 전달하세요. 최근 메일 전체 요약에는 사용하지 마세요.",
              lambda a: search.answer_question(a["question"], indexed, llm_call), schema("question", "사용자 원래 질문")),
        Skill("summarize_recent_mail", "수신 시각 기준 최신 12통을 실제 본문으로 요약합니다. 메일 수와 기간 및 원문 출처를 반환합니다. 인자 없음.",
              lambda _: search._recent_summary(indexed, llm_call), {"type": "object", "properties": {}, "additionalProperties": False}),
        Skill("get_tree", "실제 업무 목록과 ID, 첨부 ID를 조회합니다. 업무 이름만 알고 ID를 모를 때 먼저 사용하세요.", tree),
        Skill("get_case_emails", "조회한 case_id의 실제 메일 본문과 수신일을 타임라인으로 반환합니다.", case_emails, schema("case_id", "get_tree에서 확인한 ID")),
        Skill("get_attachment_text", "조회한 attachment_id의 실제 문서 전문을 읽습니다.", attachment, schema("attachment_id", "get_tree에서 확인한 첨부 ID")),
    ]
