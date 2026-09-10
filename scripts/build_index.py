"""메일 원본을 건 단위 색인으로 재조립한다.

원본 ``data/mails.json``은 읽기만 한다. 분류 정답지인 ``_case``는 사용하지
않으며, 회신 관계를 뼈대로 삼고 제목 표기·업무 생애주기·시간 근접성을
결합해 입력 순서와 무관한 결과를 만든다.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 제목의 업무 표기는 흔들리지만, 아래 값들은 동일한 업무 개체를 가리킨다.
# 이는 건을 직접 열거하는 규칙이 아니라 표기 정규화 경계다.
_TOPIC_PATTERNS = (
    ("n cx", re.compile(r"\bn\s*cx\b")),
    ("next w", re.compile(r"\bnext\s*w\b")),
    ("d mig", re.compile(r"\bd\s*mig\b")),
    ("esg공시", re.compile(r"esg\s*공시")),
    ("고객채널tf", re.compile(r"고객채널\s*tf")),
    ("경영기획", re.compile(r"경영기획")),
    ("정보보호센터", re.compile(r"정보보호센터")),
    ("멘토 멘티", re.compile(r"멘토\s*멘티")),
)

_STOPWORDS = {
    "project", "관련", "공유", "안내", "요청", "확정", "문의", "드립니다",
    "합니다", "부탁드립니다", "부탁", "확인", "첨부", "회신", "요망", "자료",
    "회의", "일정", "보고", "공지", "업무", "참고", "전달", "검토", "결과",
    "진행", "사항", "대한", "위한", "그리고", "협조", "메일입니다", "안내드립니다",
    "안내입니다", "요청드립니다", "완료했습니다", "공지사항입니다", "재공지드립니다",
    "전달드립니다", "the", "for", "and",
}


def _norm_subject(subject: str) -> str:
    """말머리·대소문자·구분자와 자주 흔들리는 표기를 정규화한다."""
    s = subject.lower()
    s = re.sub(r"\b(?:re|fw|fwd)\s*:", " ", s)
    s = s.replace("workshop", "워크숍").replace("워크샵", "워크숍")
    s = re.sub(r"[〔〕\[\]()（）]", " ", s)
    s = re.sub(r"[_\-./]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _topic_marker(subject: str) -> str:
    """제목에서 표기 흔들림을 제거한 업무 개체 표지를 찾는다."""
    normalized = _norm_subject(subject)
    for marker, pattern in _TOPIC_PATTERNS:
        if pattern.search(normalized):
            return marker
    return ""


def _tokens(text: str) -> set[str]:
    normalized = _norm_subject(text)
    tokens = set(re.findall(r"[a-z0-9]{2,}|[가-힣]{2,}", normalized))
    return {token for token in tokens if token not in _STOPWORDS and not token.isdigit()}


def _mail_time(mail: dict) -> datetime:
    return datetime.fromisoformat(mail.get("sent_at", ""))


def _reply_components(mails: list[dict]) -> list[set[str]]:
    """회신 연결을 무방향 그래프로 보고 크기 2 이상의 연결요소를 반환한다."""
    ids = {mail["id"] for mail in mails}
    graph: dict[str, set[str]] = defaultdict(set)
    for mail in mails:
        parent = mail.get("reply_to")
        if parent in ids:
            graph[mail["id"]].add(parent)
            graph[parent].add(mail["id"])

    components = []
    unseen = set(graph)
    while unseen:
        start = min(unseen)
        stack = [start]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(sorted(graph[current] - component, reverse=True))
        unseen -= component
        if len(component) >= 2:
            components.append(component)
    return sorted(components, key=lambda ids_: min(ids_))


def _component_marker(ids: set[str], mails_by_id: dict[str, dict]) -> str:
    markers = [
        marker
        for mid in sorted(ids)
        if (marker := _topic_marker(mails_by_id[mid].get("subject", "")))
    ]
    if not markers:
        return ""
    counts = Counter(markers)
    return min(counts, key=lambda marker: (-counts[marker], marker))


def _valid_learning_batch(batch: list[dict]) -> set[str] | None:
    states = {
        state
        for mail in batch
        for state in ("학습시작", "학습현황")
        if state in _norm_subject(mail.get("subject", ""))
    }
    if len(batch) >= 2 and states == {"학습시작", "학습현황"}:
        return {mail["id"] for mail in batch}
    return None


def _learning_campaigns(mails: list[dict], assigned: set[str]) -> list[set[str]]:
    """같은 발신자의 학습 시작→현황 알림 묶음을 하나의 업무 경과로 본다.

    단순 미이수 독촉은 하단 알림으로 남겨두고, 시작과 현황이라는 두 상태가
    모두 있는 짧은 기간의 캠페인만 건으로 승격한다.
    """
    candidates: dict[str, list[dict]] = defaultdict(list)
    for mail in mails:
        if mail["id"] in assigned:
            continue
        subject = _norm_subject(mail.get("subject", ""))
        if "학습시작" in subject or "학습현황" in subject:
            candidates[mail.get("sender_email", "")].append(mail)

    campaigns = []
    for sender_mails in candidates.values():
        sender_mails.sort(key=lambda mail: (mail.get("sent_at", ""), mail["id"]))
        if not sender_mails:
            continue
        batch = [sender_mails[0]]
        for mail in sender_mails[1:]:
            if _mail_time(mail) - _mail_time(batch[-1]) <= timedelta(days=14):
                batch.append(mail)
            else:
                if valid := _valid_learning_batch(batch):
                    campaigns.append(valid)
                batch = [mail]
        if valid := _valid_learning_batch(batch):
            campaigns.append(valid)
    return campaigns


def _case_period(ids: set[str], mails_by_id: dict[str, dict]) -> tuple[datetime, datetime]:
    times = [_mail_time(mails_by_id[mid]) for mid in ids]
    return min(times), max(times)


def _expand_by_signature(
    case_sets: list[set[str]], mails: list[dict], mails_by_id: dict[str, dict]
) -> None:
    """끊긴 스레드를 반복된 고유어와 시간 근접성으로 기존 건에 편입한다."""
    assigned = set().union(*case_sets) if case_sets else set()
    # 편입된 일반 메일의 상투어가 새 대표어가 되어 오분류가 눈덩이처럼 커지지
    # 않도록, 각 건의 대표어와 기간은 확장 시작 전에 한 번만 고정한다.
    profiles = []
    for ids in case_sets:
        counts = Counter(
            token
            for mid in ids
            for token in _tokens(
                f"{mails_by_id[mid].get('subject', '')} {mails_by_id[mid].get('body', '')}"
            )
        )
        profiles.append((
            {token for token, count in counts.items() if count >= 2},
            *_case_period(ids, mails_by_id),
        ))

    for mail in sorted(mails, key=lambda item: item["id"]):
        if mail["id"] in assigned or mail.get("sender_dept") == "시스템":
            continue
        probe = _tokens(f"{mail.get('subject', '')} {mail.get('body', '')}")
        if not probe:
            continue

        candidates = []
        mail_time = _mail_time(mail)
        for index, (signature, start, end) in enumerate(profiles):
            overlap = probe & signature
            distance = min(abs(mail_time - start), abs(mail_time - end))
            if overlap and start - timedelta(days=21) <= mail_time <= end + timedelta(days=21):
                candidates.append((len(overlap), -distance.total_seconds(), -index))

        if candidates:
            index = -max(candidates)[-1]
            case_sets[index].add(mail["id"])
            assigned.add(mail["id"])


def _group_cases(mails: list[dict]) -> list[tuple[str, set[str]]]:
    """회신 그래프를 시작점으로 건 후보를 만들고 끊긴 메일을 보완한다."""
    mails_by_id = {mail["id"]: mail for mail in mails}
    components = _reply_components(mails)

    marker_to_ids: dict[str, set[str]] = defaultdict(set)
    markerless_components: list[set[str]] = []
    for component in components:
        marker = _component_marker(component, mails_by_id)
        if marker:
            marker_to_ids[marker].update(component)
        else:
            markerless_components.append(component)

    assigned = set().union(*components) if components else set()
    for mail in mails:
        if mail["id"] in assigned:
            continue
        marker = _topic_marker(mail.get("subject", ""))
        # 시스템 명칭은 반복 알림에도 쓰이므로 회신 관계 없이 확장하지 않는다.
        if marker and marker in marker_to_ids and marker != "정보보호센터":
            marker_to_ids[marker].add(mail["id"])

    case_sets = list(marker_to_ids.values()) + markerless_components
    assigned = set().union(*case_sets) if case_sets else set()
    case_sets.extend(_learning_campaigns(mails, assigned))
    _expand_by_signature(case_sets, mails, mails_by_id)

    grouped = []
    for ids in case_sets:
        marker = _component_marker(ids, mails_by_id)
        if not marker and any(
            "학습시작" in _norm_subject(mails_by_id[mid].get("subject", ""))
            for mid in ids
        ):
            marker = "러닝포털 학습"
        grouped.append((marker or "업무 건", ids))
    return sorted(grouped, key=lambda item: min(item[1]))


def _make_case(title: str, ids: set[str], mails_by_id: dict[str, dict]) -> dict:
    ordered_mails = sorted(
        (mails_by_id[mid] for mid in ids),
        key=lambda mail: (mail.get("sent_at", ""), mail["id"]),
    )
    attachment_ids = list(dict.fromkeys(
        aid for mail in ordered_mails for aid in mail.get("attachments", [])
    ))
    return {
        "id": f"c-{min(ids)}",
        "title": title,
        "mail_ids": [mail["id"] for mail in ordered_mails],
        "attachment_ids": attachment_ids,
        "period": [ordered_mails[0]["sent_at"][:10], ordered_mails[-1]["sent_at"][:10]],
        "mail_type": "교육·알림" if title == "러닝포털 학습" else "프로젝트",
        "summary": " ".join(mail.get("body", "")[:60] for mail in ordered_mails[:3]),
    }


def build_index(mails: list, attachments: list) -> dict:
    """메일과 첨부 메타데이터에서 재현 가능한 읽기 전용 색인을 만든다."""
    mails_by_id = {mail["id"]: mail for mail in mails}
    grouped = _group_cases(mails)
    cases = [_make_case(title, ids, mails_by_id) for title, ids in grouped]
    case_mail_ids = {mid for case in cases for mid in case["mail_ids"]}

    attachment_texts = {}
    for attachment in sorted(attachments, key=lambda item: item["id"]):
        raw_path = Path(attachment["path"])
        path = raw_path if raw_path.is_absolute() else ROOT / raw_path
        attachment_texts[attachment["id"]] = _extract_text(path, attachment["mime"])

    non_cases = []
    for mail in sorted(mails, key=lambda item: (item.get("sent_at", ""), item["id"])):
        if mail["id"] in case_mail_ids:
            continue
        kind = "alert" if mail.get("sender_dept") == "시스템" else "misc"
        non_cases.append({"id": mail["id"], "subject": mail["subject"], "type": kind})

    return {
        "cases": cases,
        "attachment_texts": attachment_texts,
        "version_groups": _detect_versions(attachments),
        "non_cases": non_cases,
        "attachments": attachments,
    }


def _extract_text(path: Path, mime: str) -> str:
    if mime.endswith("pdf"):
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)

    from openpyxl import load_workbook

    workbook = load_workbook(str(path), read_only=True, data_only=True)
    try:
        rows = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                rows.append(" | ".join(str(cell) for cell in row if cell is not None))
        return "\n".join(rows)
    finally:
        workbook.close()


def _version_identity(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"(?:[_\-\s]*v\d+)+", "", stem)
    stem = re.sub(r"(?:[_\-\s]*(?:최종(?:본|안|명단)?|final))+$", "", stem)
    return re.sub(r"[_\-\s]+", " ", stem).strip()


def _version_rank(attachment: dict) -> tuple[int, int, int, str, str]:
    filename = Path(attachment["filename"]).stem.lower()
    versions = [int(value) for value in re.findall(r"(?:^|[_\-\s])v(\d+)", filename)]
    dates = [int(value) for value in re.findall(r"(?<!\d)(20\d{4,6})(?!\d)", filename)]
    return (
        1 if "최종" in filename or "final" in filename else 0,
        max(versions, default=0),
        max(dates, default=0),
        filename,
        attachment["id"],
    )


def _detect_versions(attachments: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for attachment in attachments:
        groups[_version_identity(attachment["filename"])].append(attachment)

    version_groups = []
    for doc, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        ordered = sorted(items, key=_version_rank)
        version_groups.append({
            "doc": doc,
            "ids": [item["id"] for item in ordered],
            "latest": ordered[-1]["id"],
        })
    return version_groups


def main() -> None:
    source = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
    result = build_index(source["mails"], source["attachments"])
    (DATA / "indexed.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"cases: {len(result['cases'])} / non_cases: {len(result['non_cases'])} "
        f"/ versions: {len(result['version_groups'])}"
    )
    print("→ data/indexed.json 저장 완료")


if __name__ == "__main__":
    main()
