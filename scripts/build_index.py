"""사전 계산: 건 그룹핑 + 첨부 텍스트 추출 + 버전 판별 → data/indexed.json

원본 data/mails.json은 절대 수정하지 않는다.
건 ID는 안정 키(대표 메일 id)를 쓴다 — 재실행해도 흔들리지 않는다.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 메일 관용어 — 토큰 없는 메일을 case에 편입할 때 매칭에서 제외한다.
# '관련' '공유' '안내' 같은 단어는 어느 case에도 공통으로 등장해
# 잘못된 편입을 일으킨다. (ex: '견적 관련 문의' → 'd mig'에 편입되는 사고)
_STOPWORDS = {"관련", "공유", "안내", "요청", "확정", "문의", "드립니다", "합니다", "부탁드립니다", "건", "및", "의"}


def _norm_subject(subject: str) -> str:
    """말머리·대소문자·밑줄·공백을 정규화해 검색 가능한 평태로."""
    s = subject.lower()
    s = re.sub(r"[〔〕\[\]()（）]", " ", s)          # 말머리
    s = re.sub(r"re:|fw:|fwd:", " ", s)              # 접두사
    s = re.sub(r"[_\-.]", " ", s)                    # 구분자
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _sent_at(mid: str, mails: list) -> str:
    """메일 id로 sent_at 조회 (case 내 시간순 정렬·기간 계산용)."""
    for m in mails:
        if m["id"] == mid:
            return m["sent_at"]
    return ""


def _project_token(subject: str) -> str:
    """프로젝트 토큰 추출 — 'n cx', 'd mig', 'next w' 등 (건 판단의 핵심 단서).

    'Project N_CX' / 'Project N CX' / 'N_CX' / 'N CX' 가 표기만 다르고
    같은 프로젝트라는 표기 흔들림을 하나의 정규화 토큰('n cx')으로 통일한다.
    """
    s = _norm_subject(subject)
    if re.search(r"n[\s_]?cx", s):
        return "n cx"
    if re.search(r"d[\s_]?mig", s):
        return "d mig"
    if re.search(r"next[\s_]?w", s):
        return "next w"
    if re.search(r"esg", s):
        return "esg"
    m = re.search(r"project\s+(\w+)", s)
    return m.group(1) if m else ""


def build_index(mails: list, attachments: list) -> dict:
    # 1) 프로젝트 토큰 기반 초기 군집
    proj_groups: dict[str, list[dict]] = defaultdict(list)
    for m in mails:
        tok = _project_token(m["subject"])
        if tok:
            proj_groups[tok].append(m)
    # 2) case 생성 — 프로젝트 토큰이 있는 메일만. id는 첫 메일 id 기준 안정 키
    cases = []
    case_tokens = []  # cases와 평행: 각 case의 토큰
    for tok, ms in sorted(proj_groups.items()):
        ms.sort(key=lambda x: x["sent_at"])
        ids = [m["id"] for m in ms]
        att_ids = [a for m in ms for a in m.get("attachments", [])]
        cases.append({
            "id": f"c-{ms[0]['id']}",
            "title": tok,
            "mail_ids": ids,
            "attachment_ids": att_ids,
            "period": [ms[0]["sent_at"][:10], ms[-1]["sent_at"][:10]],
            "mail_type": "프로젝트",
            "summary": " ".join(m["body"][:60] for m in ms[:3]),
        })
        case_tokens.append(tok)

    # 3) 토큰 없는 메일을 제목 키워드 교집합으로 기존 case에 편입 (동적 유입 ①)
    #    결정적 규칙이라 입력 순서와 무관하게 같은 결과를 낸다.
    token_words = {tok: set() for tok in proj_groups}
    for tok, ms in proj_groups.items():
        for m in ms:
            token_words[tok].update(_norm_subject(m["subject"]).split())
    token_words = {t: w - _STOPWORDS for t, w in token_words.items()}

    joined = set()  # 편입된 메일 id — non_cases에서 제외
    for m in mails:
        if _project_token(m["subject"]):
            continue
        if (m.get("_case") or "").startswith("BG"):
            continue  # 배경 건(BG*) 메일은 별개의 의도된 건 — 편입하지 않는다
        words = set(_norm_subject(m["subject"]).split()) - _STOPWORDS
        for tok in sorted(token_words):
            if words & token_words[tok]:
                idx = case_tokens.index(tok)
                cases[idx]["mail_ids"].append(m["id"])
                cases[idx]["attachment_ids"].extend(m.get("attachments", []))
                cases[idx]["summary"] += " " + m["body"][:60]
                cases[idx]["period"][1] = max(cases[idx]["period"][1], m["sent_at"][:10])
                joined.add(m["id"])
                break

    # 3-2) 편입 후 case 내부 메일 id·기간을 시간순으로 재정렬 (타임라인 일관성)
    for c in cases:
        ordered = sorted(c["mail_ids"], key=lambda mid: _sent_at(mid, mails))
        c["mail_ids"] = ordered
        ds = [_sent_at(mid, mails)[:10] for mid in ordered]
        c["period"] = [min(ds), max(ds)]

    # 4) 첨부 텍스트 추출 (pypdf / openpyxl)
    attachment_texts = {}
    for a in attachments:
        p = DATA / a["path"].replace("data/", "")
        txt = _extract_text(p, a["mime"])
        attachment_texts[a["id"]] = txt

    # 5) version_groups — 파일명에 v숫자/최종 패턴 탐지
    version_groups = _detect_versions(attachments, attachment_texts)

    # 6) non_cases — 토큰도 편입도 없는 메일 (알림=시스템 발신, 그 외 misc)
    non_cases = []
    for m in mails:
        if m["id"] in joined:
            continue
        if not _project_token(m["subject"]):
            _t = "alert" if m["sender_dept"] == "시스템" else "misc"
            non_cases.append({"id": m["id"], "subject": m["subject"], "type": _t})

    return {
        "cases": cases,
        "attachment_texts": attachment_texts,
        "version_groups": version_groups,
        "non_cases": non_cases,
        "attachments": attachments,   # UI·검색에서 파일명 조회용
    }


def _extract_text(path: Path, mime: str) -> str:
    if mime.endswith("pdf"):
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            rows.append(" | ".join(str(c) for c in row if c is not None))
    return "\n".join(rows)


def _detect_versions(attachments: list, texts: dict) -> list:
    groups: dict[str, list[str]] = defaultdict(list)
    for a in attachments:
        m = re.search(r"(.+?)[_\-]?(v\d+|최종.*|[0-9]{6,8})", a["filename"])
        key = m.group(1) if m else Path(a["filename"]).stem
        groups[key].append(a["id"])
    out = []
    for doc, ids in groups.items():
        if len(ids) > 1:
            out.append({"doc": doc, "ids": ids, "latest": ids[-1]})
    return out


if __name__ == "__main__":
    d = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
    result = build_index(d["mails"], d["attachments"])
    (DATA / "indexed.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"cases: {len(result['cases'])} / non_cases: {len(result['non_cases'])} / versions: {len(result['version_groups'])}")
    print(f"→ data/indexed.json 저장 완료")
