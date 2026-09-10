"""건 단위 재조립 (장면 2) — indexed.json → 사안 카드 + 신메일 증분 편입 판단.

원칙:
- `indexed.json`은 읽기 전용으로만 사용한다 (원본 메일함 무수정).
- LLM 호출이 기본 경로이며, 실패 시 토큰·키워드 폴백으로도 배정을 결정한다.
- 저장은 인메모리 — DB/SQLite를 쓰지 않는다.
"""
import json
import re
from pathlib import Path

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


def _tokens(text: str) -> set[str]:
    """제목·본문에서 비교 가능한 토큰 집합 추출 (영문·숫자·한글 2자 이상)."""
    if not text:
        return set()
    toks = re.findall(r"[a-zA-Z0-9]{2,}|[가-힣]{2,}", text.lower())
    stopwords = {
        "project", "학교", "주세요", "드립니다", "합니다", "부탁", "문의", "요청",
        "관련", "안내", "공유", "건", "님", "및", "등", "첨부", "확인",
        "re", "fw", "fwd", "the", "for", "and",
    }
    return {t for t in toks if t not in stopwords and not t.isdigit()}


def _token_intersect_score(new_mail: dict, case_title: str, case_mails: list[dict]) -> int:
    """신메일 제목·본문과 건 제목·소속 메일 제목의 토큰 교집합 점수."""
    probe = _tokens(f"{new_mail.get('subject', '')} {new_mail.get('body', '')}")
    targets = _tokens(case_title)
    for m in case_mails:
        targets |= _tokens(m.get("subject", ""))
    return len(probe & targets)


def classify_new_mail(new_mail: dict, indexed: dict, llm_call) -> str:
    """신메일 1통을 기존 건 id / 'NEW_CASE'로 배정한다 (증분 편입).

    - LLM 호출이 기본 경로: 반환된 문자열에서 건 id를 찾아 그대로 배정.
    - LLM 실패(예외·미배정 문자열) 시 토큰·키워드 폴백으로 결정:
      교집합 점수가 가장 높은 기존 건으로 배정하고, 후보가 없으면 'NEW_CASE'.
    """
    # 0) LLM 호출이 먼저 — 실패 시 폴백
    try:
        answer = llm_call(
            "새 메일이 도착했다. 어떤 기존 건에 배정하겠는가?\n"
            f"건 id 목록: {[(c['id'], c['title']) for c in indexed.get('cases', [])]}\n"
            f"새 메일: {new_mail.get('subject', '')} / {new_mail.get('body', '')}\n"
            "배정 건 id:"
        ).strip()
    except Exception:
        answer = ""

    if answer:
        for case in indexed.get("cases", []):
            cid = case.get("id", "")
            if cid and cid in answer:
                return cid

    # 1) 토큰·키워드 폴백 — LLM 없이도 배정이 결정되어야 한다
    mails_by_id = _mails_from(indexed)
    best_id, best_score = "", 0
    for case in indexed.get("cases", []):
        case_mails = [mails_by_id[i] for i in case.get("mail_ids", []) if i in mails_by_id]
        score = _token_intersect_score(new_mail, case.get("title", ""), case_mails)
        if score > best_score:
            best_id, best_score = case["id"], score
    if best_score > 0:
        return best_id
    return "NEW_CASE"