"""업무맥락 분류 공유 규칙 — 배치(scripts/build_index)와 증분(app/grouping)이
같은 정규화 경계·대표어·시간 근접·마커·학습 캠페인 규칙을 공유한다.

왜 공유 모듈인가: 배치와 증분이 각자 규칙을 복제하면 한쪽만 바뀌었을 때
같은 메일이 다른 결론을 받는 '오분류 드리프트'가 생긴다. 이 모듈이 단일
출처(single source of truth)로, 두 경로 모두 여기를 부른다.

원칙(설계문서·AGENTS.md):
- 표기 정규화는 결정 근거가 아니라 '업무 개체 식별' 경계다.
- 대표어는 '건에서 2회 이상 반복된 고유 토큰'만 쓴다 (상투어·반복 알림 제외).
- 시간은 결정 근거가 아니다 — 내용 신호(대표어)가 있을 때 후보를 좁히는 보조 단서.
- 시스템 발신 알림 중 '학습 시작↔현황' 두 상태가 있는 짧은 캠페인만 건으로 승격.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 제목의 업무 표기는 흔들리지만, 아래 값들은 동일한 업무 개체를 가리킨다.
# 이는 '건을 직접 열거하는 규칙'이 아니라 표기 정규화 경계다.
TOPIC_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("n cx", re.compile(r"\bn\s*cx\b")),
    ("next w", re.compile(r"\bnext\s*w\b")),
    ("d mig", re.compile(r"\bd\s*mig\b")),
    ("esg공시", re.compile(r"esg\s*공시")),
    ("고객채널tf", re.compile(r"고객채널\s*tf")),
    ("경영기획", re.compile(r"경영기획")),
    ("정보보호센터", re.compile(r"정보보호센터")),
    ("멘토 멘티", re.compile(r"멘토\s*멘티")),
)

# 시스템 명칭/알림 상투어 — 특정 업무를 대표하지 않는 말.
SYSTEM_MARKERS = {"정보보호센터"}

STOPWORDS = {
    "project", "관련", "공유", "안내", "요청", "확정", "문의", "드립니다",
    "합니다", "부탁드립니다", "부탁", "확인", "첨부", "회신", "요망", "자료",
    "회의", "일정", "보고", "공지", "업무", "참고", "전달", "검토", "결과",
    "진행", "사항", "대한", "위한", "그리고", "협조", "메일입니다", "안내드립니다",
    "안내입니다", "요청드립니다", "완료했습니다", "공지사항입니다", "재공지드립니다",
    "전달드립니다", "the", "for", "and", "학교", "주세요", "건", "님", "및", "등",
    "re", "fw", "fwd",
}

# 시간 보조 단서: 대표어 1개가 겹칠 때 후보를 좁히는 창 (날짜 단위)
TIME_WINDOW_DAYS = 21
# 학습 캠페인: 같은 발신자 시작→현황 사이 허용 간격
LEARNING_CAMPAIGN_GAP_DAYS = 14

# 분류 결과 3분기 (설계문서 '동적 유입 원칙')
DECISION_EXISTING = "existing"
DECISION_NEW_CASE = "new_case"
DECISION_NON_CASE = "non_case"


def normalize_subject(subject: str) -> str:
    """말머리·대소문자·구분자와 흔들리는 표기를 정규화한다 (공유 경계)."""
    s = (subject or "").lower()
    s = re.sub(r"\b(?:re|fw|fwd)\s*:", " ", s)
    s = s.replace("workshop", "워크숍").replace("워크샵", "워크숍")
    s = re.sub(r"[〔〕\[\]()（）]", " ", s)
    s = re.sub(r"[_\-./]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def topic_marker(subject: str) -> str:
    """제목에서 표기 흔들림을 제거한 업무 개체 표지를 찾는다."""
    normalized = normalize_subject(subject)
    for marker, pattern in TOPIC_PATTERNS:
        if pattern.search(normalized):
            return marker
    return ""


def tokens(text: str) -> set[str]:
    """제목·본문에서 비교 가능한 토큰 집합 (상투어·숫자 제외)."""
    if not text:
        return set()
    normalized = normalize_subject(text)
    found = re.findall(r"[a-z0-9]{2,}|[가-힣]{2,}", normalized)
    return {token for token in found if token not in STOPWORDS and not token.isdigit()}


def case_signatures(indexed: dict, mails_by_id: dict) -> dict[str, set[str]]:
    """각 건의 대표어 집합 — 건 메일에서 2회 이상 반복되는 고유 토큰."""
    signatures = {}
    for case in indexed.get("cases", []):
        counts: Counter = Counter()
        for mid in case.get("mail_ids", []):
            mail = mails_by_id.get(mid)
            if mail is None:
                continue
            counts.update(tokens(f"{mail.get('subject', '')} {mail.get('body', '')}"))
        signatures[case["id"]] = {token for token, count in counts.items() if count >= 2}
    return signatures


def case_periods(indexed: dict, mails_by_id: dict) -> dict[str, tuple[datetime, datetime]]:
    """각 건의 시작·종료 시각 (시간 보조 단서에 사용)."""
    periods = {}
    for case in indexed.get("cases", []):
        times = [
            datetime.fromisoformat(mails_by_id[mid]["sent_at"])
            for mid in case.get("mail_ids", [])
            if mid in mails_by_id and mails_by_id[mid].get("sent_at")
        ]
        if times:
            periods[case["id"]] = (min(times), max(times))
    return periods


def mail_time(mail: dict) -> datetime:
    return datetime.fromisoformat(mail.get("sent_at", ""))


def is_learning_campaign(subject: str) -> bool:
    """시스템 발신 학습 캠페인(학습시작/학습현황)인지 판단 (공유 경계)."""
    normalized = normalize_subject(subject)
    return "학습시작" in normalized or "학습현황" in normalized