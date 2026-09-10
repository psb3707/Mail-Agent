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


def _norm_subject(subject: str) -> str:
    """말머리·대소문자·밑줄·공백을 정규화해 검색 가능한 평태로."""
    s = subject.lower()
    s = re.sub(r"[〔〕\[\]()（）]", " ", s)          # 말머리
    s = re.sub(r"re:|fw:|fwd:", " ", s)              # 접두사
    s = re.sub(r"[_\-.]", " ", s)                    # 구분자
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _project_token(subject: str) -> str:
    """프로젝트 토큰 추출 — 'n cx', 'd mig', 'next w' 등 (건 판단의 핵심 단서)."""
    s = _norm_subject(subject)
    m = re.search(r"(project\s+[\w]+|n[\s_]?cx|d[\s_]?mig|next[\s_]?w|esg)", s)
    return m.group(1) if m else ""


def build_index(mails: list, attachments: list) -> dict:
    # 1) 프로젝트 토큰 기반 초기 군집
    proj_groups: dict[str, list[str]] = defaultdict(list)
    for m in mails:
        tok = _project_token(m["subject"])
        if tok:
            proj_groups[tok].append(m)
    # 2) case 생성 — 프로젝트 토큰이 있는 메일만. id는 첫 메일 id 기준 안정 키
    cases = []
    for idx, (tok, ms) in enumerate(sorted(proj_groups.items())):
        ms.sort(key=lambda x: x["sent_at"])
        ids = [m["id"] for m in ms]
        att_ids = [a for m in ms for a in m.get("attachments", [])]
        cases.append({
            "id": f"c-{ms[0]['id']}",
            "title": tok if tok else "기타",
            "mail_ids": ids,
            "attachment_ids": att_ids,
            "period": [ms[0]["sent_at"][:10], ms[-1]["sent_at"][:10]],
            "mail_type": "프로젝트",
            "summary": " ".join(m["body"][:60] for m in ms[:3]),
        })

    # 3) 첨부 텍스트 추출 (pypdf / openpyxl)
    attachment_texts = {}
    for a in attachments:
        p = DATA / a["path"].replace("data/", "")
        txt = _extract_text(p, a["mime"])
        attachment_texts[a["id"]] = txt

    # 4) version_groups — 파일명에 v숫자/최종 패턴 탐지
    version_groups = _detect_versions(attachments, attachment_texts)

    # 5) non_cases — 프로젝트 토큰 없는 메일 (알림=시스템 발신, 그 외 misc)
    non_cases = []
    for m in mails:
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
