"""버전 판별 (장면 4) — 같은 문서 버전 계열 → 최신본 + 달라진 항목 요약.

LLM 없이도(규칙 폴백) 동작한다 — `attachment_texts`에서 숫자·단위가 있는 줄을 골라
최신본 vs 직전 버전의 차이를 요약한다.
"""
import re


def _version_key(filename: str) -> int:
    """파일명에서 버전 번호 추출. v3 → 3, v2 → 2. 없으면 '최종' 포함 시 99, 없으면 0."""
    m = re.search(r"v(\d+)", filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if "최종" in filename:
        return 99
    if "1차" in filename or "2차" in filename or "3차" in filename:
        # 파일명에 차수 표기 — '3차' > '2차' > '1차'
        m2 = re.search(r"([123])차", filename)
        if m2:
            return int(m2.group(1))
    return 0


def _file_for(attachments: list[dict], aid: str) -> str:
    for a in attachments:
        if a["id"] == aid:
            return a.get("filename", aid)
    return aid


def _pick_latest(ids: list[str], attachments: list[dict]) -> str:
    """id 목록 중 버전 번호가 가장 큰(=최신) id 반환. 동률이면 마지막."""
    return max(ids, key=lambda aid: (_version_key(_file_for(attachments, aid)), 0))


def _diff_summary(latest_text: str, prev_text: str) -> str:
    """최신본 vs 직전 본문을 규칙으로 비교해 달라진 핵심 항목 요약.

    두 본문의 줄 중 서로 다른 값이 있으면 그 줄을 추출하고,
    없으면 최신본의 값(금액·단가·업체)만 요약한다.
    """
    def _lines(text: str) -> list[str]:
        if not text:
            return []
        return [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]

    latest, prev = _lines(latest_text), _lines(prev_text)
    # 실제 값(숫자·단위·업체)이 있는 라인
    def _valuable(ln: str) -> bool:
        return any(ch.isdigit() for ch in ln) or any(
            k in ln for k in ("주)", "원", "%", "단가", "금액", "VAT", "호차", "명", "건", "일자", "업체")
        )

    lv = [ln for ln in latest if _valuable(ln)]
    pv = [ln for ln in prev if _valuable(ln)]

    changed = []
    for ln in lv:
        if ln not in pv:
            changed.append(ln)

    # 변화가 없어도 최신본의 값은 보여줌 (문구로 명시)
    if changed:
        head = f"[vs 이전 버전] {changed[0]}"
        tail = [ln for ln in changed[1:4]]
        return " · ".join([head] + tail) if tail else head
    if lv:
        return f"[최신본] {lv[0]}"
    return "내용 항목은 파일을 열어 확인 필요"


def version_compare(indexed: dict) -> list[dict]:
    """indexed.version_groups[] → 최신본 + diff_summary + evidence 리스트.

    반환 각 항목: {"doc", "ids", "latest", "diff_summary", "evidence"}.
    latest는 version_groups의 값이 아니라 **본문에서 버전 번호를 재판별**한다
    (indexed.json의 latest가 잘못된 경우 보정).
    """
    att_texts = indexed.get("attachment_texts", {})
    attachments = indexed.get("attachments", [])
    groups = indexed.get("version_groups", [])
    if not groups:
        return []

    out = []
    for g in groups:
        ids = list(g.get("ids", []))
        if len(ids) < 2:  # 버전 계열이 아니면 제외 (완료 조건 3)
            continue

        latest = _pick_latest(ids, attachments)
        prev_ids = [i for i in ids if i != latest]
        prev = prev_ids[-1] if prev_ids else latest

        latest_text = att_texts.get(latest, "")
        prev_text = att_texts.get(prev, "") if prev != latest else ""

        diff = _diff_summary(latest_text, prev_text)
        evidence = [
            att_texts.get(i, "")[:200] for i in ([prev, latest] if prev != latest else [latest])
        ]

        out.append({
            "doc": g.get("doc", ""),
            "ids": ids,
            "latest": latest,
            "diff_summary": diff,
            "evidence": evidence,
        })
    return out