"""건 단위 재조립 (장면 2) — indexed.json → 사안 카드 + 신메일 증분 편입 판단.

원칙:
- `indexed.json`은 읽기 전용으로만 사용한다 (원본 메일함 무수정).
- LLM 호출이 기본 경로이며, 실패 시 규칙 폴백(공유 규칙)으로도 배정을 결정한다.
- 저장은 인메모리 — DB/SQLite를 쓰지 않는다.
- 분류 규칙은 `app/classify_rules.py`가 단일 출처 — 배치(build_index)와 공유한다.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from app import classify_rules
from app.classify_rules import (
    DECISION_EXISTING,
    DECISION_NEW_CASE,
    DECISION_NON_CASE,
)

DATA = Path(__file__).resolve().parent.parent / "data"


class _MailsLoader:
    """data/mails.json 로더 — indexed.json에 mail 원문이 없을 때 보조 로드.

    indexed.json에는 cases[].mail_ids만 있고 원문 본문·발신자가 없어,
    "마지막 답변 확인"(latest_*)을 채우려면 원본 메일함을 읽어야 한다.
    메일함은 읽기 전용 — 수정하지 않는다.
    """
    _cache: dict | None = None

    @classmethod
    def load(cls) -> dict[str, dict]:
        if cls._cache is None:
            raw = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
            cls._cache = {m["id"]: m for m in raw["mails"]}
        return cls._cache


def _mails_from(indexed: dict) -> dict[str, dict]:
    """indexed에 mail 원문이 있으면 그것을, 없으면 data/mails.json에서 로드."""
    if indexed.get("mails"):
        return {m["id"]: m for m in indexed["mails"]}
    return _MailsLoader.load()


def reassemble(indexed: dict) -> list[dict]:
    """indexed의 cases[]를 건 카드 리스트로 변환한다.

    카드: {"id", "title", "mails", "attachments", "period", "mail_type",
           "latest_sender", "latest_body", "latest_at"}
    - mails: 원본 mail dict (sent_at 오름차순)
    - latest_*: 카드의 마지막 메일(가장 최신)에서 추출 — "마지막 답변 확인"의 핵심
    """
    mails_by_id = _mails_from(indexed)
    cards = []
    for case in indexed.get("cases", []):
        mail_ids = case.get("mail_ids", [])
        case_mails = [mails_by_id[i] for i in mail_ids if i in mails_by_id]
        case_mails.sort(key=lambda m: m.get("sent_at", ""))
        last = case_mails[-1] if case_mails else None
        cards.append({
            "id": case.get("id", ""),
            "title": case.get("title", ""),
            "mails": case_mails,
            "attachments": case.get("attachment_ids", []),
            "period": case.get("period", []),
            "mail_type": case.get("mail_type", ""),
            "latest_sender": last["sender_name"] if last else "",
            "latest_body": last["body"] if last else "",
            "latest_at": last["sent_at"] if last else "",
        })
    return cards


def _norm_subject(subject: str) -> str:
    """말머리·대소문자·구분자와 흔들리는 표기 정규화 —공유 규칙 위임."""
    return classify_rules.normalize_subject(subject)


def _topic_marker(subject: str) -> str:
    """제목에서 표기 흔들림을 제거한 업무 개체 표지를 찾는다."""
    return classify_rules.topic_marker(subject)


def _tokens(text: str) -> set[str]:
    """제목·본문 비교 토큰 — 공유 규칙(상투어·숫자 제외) 위임."""
    return classify_rules.tokens(text)


def _case_signatures(indexed: dict, mails_by_id: dict) -> dict[str, set[str]]:
    """각 건의 대표어 집합 — 공유 규칙 위임 (2회+ 반복 고유 토큰)."""
    return classify_rules.case_signatures(indexed, mails_by_id)


def _case_periods(indexed: dict, mails_by_id: dict) -> dict[str, tuple]:
    """각 건의 시작·종료 시각 — 시간 보조 단서(끊긴 스레드 보완)에 쓴다."""
    periods = {}
    for case in indexed.get("cases", []):
        times = [
            mails_by_id[mid]["sent_at"]
            for mid in case.get("mail_ids", [])
            if mid in mails_by_id and mails_by_id[mid].get("sent_at")
        ]
        if times:
            periods[case["id"]] = (
                datetime.fromisoformat(min(times)),
                datetime.fromisoformat(max(times)),
            )
    return periods


def _is_learning_campaign(new_mail: dict) -> bool:
    """시스템 발신 학습 캠페인(학습시작/학습현황)인지 — 공유 규칙 위임."""
    return classify_rules.is_learning_campaign(new_mail.get("subject", ""))


def classify_new_mail(new_mail: dict, indexed: dict, llm_call) -> dict:
    """신메일 1통을 3분기로 분류하고 배정 건 id를 반환한다 (증분 편입).

    반환: {"decision": "EXISTING"|"NEW_CASE"|"NON_CASE", "case_id": str}
      - EXISTING: 기존 건에 배정 (case_id: 실제 건 id)
      - NEW_CASE: 새 업무 건 후보 (case_id: "")
      - NON_CASE: 비건 (시스템 알림·단발 공지, case_id: "")

    LLM 호출이 기본 경로이고, 실패 시 규칙 폴백 순서는 다음과 같다.
    1. 제목 업무 마커(표기 흔들림 정규화) → 해당 건 직배정
       (정보보호센터는 반복 알림에도 쓰이는 시스템 명칭이라 배치와 동일하게 제외)
    2. 건 대표어(2회+ 반복 토큰) 교집합이 2개 이상 → 최고 점수 건 배정
    3. 대표어 1개 + 시간 근접(건 기간 ±21일) → 끊긴 스레드 보완 배정
       (build_index._expand_by_signature와 동일한 보조 단서 — 시각은 결정 근거가
       아니라 내용 신호가 있을 때 후보를 좁히는 보조 단서로만 쓴다)
    4. 그 외 — 시스템 알림(NON_CASE) / 새 업무 건 후보(NEW_CASE)로 분리한다
    """
    # 0) 시스템 발신 알림은 학습 캠페인(시작/현황)이 아니면 무조건 비건이다.
    #    (배치 _group_cases와 동일 — 시스템 명칭이 알림에도 쓰이므로 회신 없이
    #     건으로 승격하지 않는다. LLM 판단보다 먼저 확정해 오염을 막는다.)
    is_system = new_mail.get("sender_dept") == "시스템"
    if is_system and not _is_learning_campaign(new_mail):
        return {"decision": DECISION_NON_CASE, "case_id": ""}

    # 1) LLM 호출 — 성공 시 그 판단을 존중 (시스템 알림은 위에서 이미 비건 확정)
    try:
        answer = llm_call(_classify_prompt(new_mail, indexed)).strip()
    except Exception:
        answer = ""

    if answer:
        for case in indexed.get("cases", []):
            cid = case.get("id", "")
            if cid and cid in answer:
                return {"decision": DECISION_EXISTING, "case_id": cid}

    # 2) 제목 업무 마커 (N_CX ↔ N CX 등 표기 흔들림 정규화) → 직접배정
    marker = _topic_marker(new_mail.get("subject", ""))
    if marker and marker != "정보보호센터":
        for case in indexed.get("cases", []):
            if _topic_marker(case.get("title", "")) == marker:
                return {"decision": DECISION_EXISTING, "case_id": case["id"]}

    # 2) 건 대표어 교집합 — 상투어 1개만으로 배정하지 않는다 (≥2 필요)
    mails_by_id = _mails_from(indexed)
    signatures = _case_signatures(indexed, mails_by_id)
    probe = _tokens(f"{new_mail.get('subject', '')} {new_mail.get('body', '')}")
    best_id, best_score = "", 0
    for case in indexed.get("cases", []):
        overlap = len(probe & signatures.get(case["id"], set()))
        if overlap > best_score:
            best_id, best_score = case["id"], overlap
    if best_score >= 2:
        return {"decision": DECISION_EXISTING, "case_id": best_id}

    # 3) 대표어 1개 + 시간 근접 — 끊긴 스레드(시각 보조 단서)로 보완
    if probe:
        mail_time = None
        try:
            mail_time = datetime.fromisoformat(new_mail.get("sent_at", ""))
        except (ValueError, TypeError):
            mail_time = None
        periods = _case_periods(indexed, mails_by_id)
        if mail_time:
            for case in indexed.get("cases", []):
                cid = case.get("id", "")
                overlap = len(probe & signatures.get(cid, set()))
                if overlap < 1:
                    continue
                period = periods.get(cid)
                if not period:
                    continue
                start, end = period
                if start - timedelta(days=21) <= mail_time <= end + timedelta(days=21):
                    return {"decision": DECISION_EXISTING, "case_id": cid}

    # 그 외 — 시스템 알림은 비건, 그 외 단발·새 업무는 새 건 후보로 분리한다
    if is_system:
        return {"decision": DECISION_NON_CASE, "case_id": ""}
    return {"decision": DECISION_NEW_CASE, "case_id": ""}


def _classify_prompt(new_mail: dict, indexed: dict) -> str:
    """LLM 프롬프트 — 건 제목만이 아니라 대표어·기간 요약을 제공한다."""
    mails_by_id = _mails_from(indexed)
    signatures = _case_signatures(indexed, mails_by_id)
    case_lines = []
    for case in indexed.get("cases", []):
        cid = case.get("id", "")
        period = case.get("period", [])
        rep = sorted(signatures.get(cid, set()))[:8]
        case_lines.append(
            f"- {cid}: {case.get('title', '')} / 대표어: {', '.join(rep) or '없음'} / 기간: {period}"
        )
    return (
        "새 메일이 도착했습니다. 어떤 기존 건에 배정하겠습니까?"
        " (답변: 기존 건 id 또는 '새 건')\n건 목록:\n"
        + "\n".join(case_lines)
        + "\n새 메일: " + new_mail.get("subject", "")
        + " / " + new_mail.get("body", "")
        + "\n배정 건 id:"
    )