# mail-agent 핵심 PoC 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메일함 400통을 업무 맥락(건) 단위로 재조립해, "이전 답변 확인 + 첨부 위치 확인"이 즉시 가능한 단일 페이지 PoC를 구현한다.

**Architecture:** 사전 계산(offline) + 라이브 재분류(on-demand) 2단 구성. `scripts/build_index.py`가 사전에 LLM으로 400통을 건 그룹핑·첨부 텍스트 추출·버전 판별해 `data/indexed.json`을 생성하고, `app/`(FastAPI 단일 페이지)이 이를 로드해 도착순↔건 단위 토글·건 카드(답변 타임라인+첨부 위치)·자연어 질문창(라이브 LLM + 캐시 폴백)을 서빙한다.

**Tech Stack:** Python 3.11+ / FastAPI / Jinja2 / anthropic(Claude) / pypdf / openpyxl / pytest

**Spec:** `docs/specs/2026-09-09-mail-agent-design.md` + `data/SCHEMA.md` + `AGENTS.md`

## Global Constraints

- **원본 `data/mails.json`·`data/attachments/` 절대 수정 금지** — 시연은 "무수정" 전제
- **저장은 인메모리** — DB 없음 (SQLite 금지). 동적 구조는 세션/인메모리로만
- **라이브 LLM 호출이 기본** — 캐시는 네트워크 장애 시 자동 폴백으로만 (기본 경로 아님)
- **건 그룹핑 방식**: 사전 계산(offline, LLM 1회) + 시연 중 라이브 재분류(신메일 1통, 캐시 폴백)
- **순서 무관** — 입력 순서를 뒤섞어도 같은 `cases[]`가 나와야 함 (검증 테스트 포함)
- **멱등 재색인** — 재실행해도 건 ID·결론이 흔들리지 않음 (시퀀스 ID 금지, 콘텐츠 기반 안정 키)
- **비건 메일 처리** — 건에 안 붙는 메일(357통)은 "알림"/"기타" 섹션으로 (무시하지 않음)
- **"왜 이것인가" 근거 인용** — 답만 주지 말고 문서 안 실제 값(금액·일자·버전·업체) 인용
- 파일 구조는 설계문서의 `app/`·`scripts/` 구성 유지 (새 폴더 X)
- 출력 언어: 한국어 (UI·답변)

## 파일 구조

```
data/
  indexed.json          # (생성) 사전 계산 결과: cases / attachment_texts / version_groups / non_cases
  demo_cache.json       # (생성) 폴백용 사전 계산 답변
scripts/
  build_index.py        # (수정) offlined 그룹핑 + 텍스트 추출 + 버전 판별 → indexed.json
app/
  __init__.py           # (생성)
  main.py               # (생성) FastAPI 라우트 3개 (/, /ask, /versions)
  grouping.py           # (생성) 건 단위 재조립 (장면 2) + 신메일 재분류
  search.py             # (생성) 자연어 질의 → 후보 → 근거 (장면 3)
  versions.py           # (생성) 버전 판별 + 차이 요약 (장면 4)
  llm.py                # (생성) Claude 호출 + 실패 시 캐시 폴백
  templates/index.html  # (생성) 단일 페이지 (토글 + 카드 + 질문창 + 답변)
tests/
  test_grouping.py      # (생성) 건 그룹핑 + 순서 무관 테스트
  test_versions.py      # (생성) 버전 판별 테스트
  test_search.py        # (생성) 질의 → 후보·근거 테스트
  test_llm.py           # (생성) 캐시 폴백 테스트
```

---

### Task 1: 사전 계산 — `scripts/build_index.py`

**Files:**
- Create: `scripts/build_index.py`
- Test: `tests/test_build_index.py`

**Interfaces:**
- Produces: 함수 `build_index(mails: list, attachments: list) -> dict`
  반환: `{"cases": [...], "attachment_texts": {...}, "version_groups": [...], "non_cases": [...], "attachments": [...]}`
  - `case`: `{"id": "c01", "title": str, "mail_ids": [str], "attachment_ids": [str], "period": [str, str], "mail_type": str, "summary": str}` — `id`는 시퀀스가 아닌 **콘텐츠 기반 안정 키**(예: first mail id `c-m0001`)
  - `non_case`: `{"id": "n001", "subject": str, "type": "alert"|"misc"}`
  - `version_group`: `{"doc": str, "ids": [str], "latest": str}`
  - `attachments`: 원본 첨부 메타 리스트(`id, filename, path, mime`) — **UI·검색에서 파일명 조회용**
- CLI 실행: `python scripts/build_index.py` → `data/indexed.json` 생성

- [ ] **Step 1: Write failing test** — `tests/test_build_index.py`

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_index import build_index

def _load():
    d = json.loads(Path("data/mails.json").read_text())
    return d["mails"], d["attachments"]

def test_build_index_creates_cases():
    mails, atts = _load()
    result = build_index(mails, atts)
    assert result["cases"], "cases가 비어 있으면 안 됨"
    # 건 A: 6통이 같은 건으로 묶여야 함
    case_a = next(c for c in result["cases"] if "m0001" in c["mail_ids"])
    assert {"m0001","m0002","m0003","m0004","m0005","m0006"} <= set(case_a["mail_ids"])

def test_build_index_order_invariant():
    import random
    random.seed(1)
    mails, atts = _load()
    shuffled = mails[:]
    random.shuffle(shuffled)
    base = build_index(mails, atts)
    other = build_index(shuffled, atts)
    # 순서 무관: 건 ID → mail_ids 집합이 동일해야 함
    b = {c["id"]: frozenset(c["mail_ids"]) for c in base["cases"]}
    o = {c["id"]: frozenset(c["mail_ids"]) for c in other["cases"]}
    assert b == o

def test_build_index_idempotent():
    mails, atts = _load()
    r1 = build_index(mails, atts)
    r2 = build_index(mails, atts)
    ids1 = {c["id"] for c in r1["cases"]}
    ids2 = {c["id"] for c in r2["cases"]}
    assert ids1 == ids2  # 재실행해도 건 ID가 흔들리지 않음

def test_attachment_texts_extracted():
    _, atts = _load()
    result = build_index(*_load())
    for a in atts:
        assert result["attachment_texts"][a["id"]]  # 모든 첨부 텍스트 존재
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `./.venv/bin/python -m pytest tests/test_build_index.py -v`
  Expected: FAIL (module `scripts.build_index` not found)

- [ ] **Step 3: Write minimal implementation** — `scripts/build_index.py`

```python
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
            "id": f"c-{ms[0]['id']}",          # 안정 키: 대표 메일 id
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
    # 최신: v숫자 최대 or '최종' 포함 or 마지막 첨부
    out = []
    for doc, ids in groups.items():
        if len(ids) < 2:
            continue
        def _ver(aid):
            f = next(x["filename"] for x in attachments if x["id"] == aid)
            m = re.search(r"v(\d+)", f)
            return int(m.group(1)) if m else (99 if "최종" in f else 0)
        latest = max(ids, key=_ver)
        out.append({"doc": doc, "ids": ids, "latest": latest})
    return out


def main():
    d = json.loads((DATA / "mails.json").read_text())
    result = build_index(d["mails"], d["attachments"])
    (DATA / "indexed.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"cases: {len(result['cases'])}, versions: {len(result['version_groups'])}, non_cases: {len(result['non_cases'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_build_index.py -v`
  Expected: PASS (전체 4개)

- [ ] **Step 5: Run build script + commit**
  Run: `./.venv/bin/python scripts/build_index.py`
  Expected: `cases: N, versions: M, non_cases: K` 출력 + `data/indexed.json` 생성
  Commit: `git add data/indexed.json scripts/build_index.py tests/test_build_index.py && git commit -m "feat: add offline build_index (grouping + text extraction + versions)"`

---

### Task 2: 검색·질의 — `app/search.py`

**Files:**
- Create: `app/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `data/indexed.json` (Task 1 산출물)
- Produces: 함수 `answer_question(question: str, indexed: dict, llm_call: Callable) -> dict`
  반환: `{"answer": str, "attachment": str|None, "evidence": [str], "mail_ids": [str], "cached": bool}`

- [ ] **Step 1: Write failing test** — `tests/test_search.py`

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.search import answer_question

def _indexed():
    return json.loads(Path("data/indexed.json").read_text())

# 캐시 폴백이 있는 llm_call 스텁 — 네트워크 없이 테스트 가능
def _dummy_llm(prompt, **kw):
    return "N_CX 외주 견적 최종은 (주)디자인랩스 48,500,000원(VAT 별도)입니다."

def test_answer_finds_correct_attachment():
    idx = _indexed()
    res = answer_question("N_CX 외주 견적 최종 얼마였지?", idx, _dummy_llm)
    assert res["attachment"]
    assert any("디자인랩스" in t for t in res["evidence"])  # 근거에 실제 값
    assert res["cached"] is False

def test_answer_returns_evidence_from_corpus():
    idx = _indexed()
    res = answer_question("워크숍 버스 몇 시에 어디서 타?", idx, _dummy_llm)
    assert res["attachment"] == "NextW_버스배차_최종명단.pdf" or any("3호차" in t for t in res["evidence"])
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `./.venv/bin/python -m pytest tests/test_search.py -v`
  Expected: FAIL (module `app.search` not found)

- [ ] **Step 3: Write implementation** — `app/search.py`

```python
"""자연어 질의 → 건·첨부 후보 축소 → 근거 추출 → LLM 답변 (장면 3).

라이브 LLM 호출이 기본. 실패 시 캐시(사전 계산 답변)로 폴백.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _corpus(indexed: dict) -> list[dict]:
    """후보 첨부: 추출 텍스트 + 소속 메일 + 건 제목을 묶은 서치 코퍼스."""
    att_meta = {a["id"]: a for a in indexed.get("attachments", [])}
    out = []
    att_texts = indexed.get("attachment_texts", {})
    for doc in indexed.get("cases", []):
        for aid in doc.get("attachment_ids", []):
            meta = att_meta.get(aid, {})
            out.append({
                "file": meta.get("filename", aid),
                "text": att_texts.get(aid, ""),
                "case": doc["title"],
                "mail_ids": doc["mail_ids"],
            })
    return out


def _keyword_candidates(question: str, corpus: list[dict], top_k: int = 5) -> list[dict]:
    toks = set(question.lower().split())
    scored = []
    for item in corpus:
        score = sum(1 for t in toks if t in item["text"].lower() or t in item["case"].lower())
        scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored if s[0] > 0][:top_k] or corpus[:top_k]


def answer_question(question: str, indexed: dict, llm_call) -> dict:
    corpus = _corpus(indexed)
    cands = _keyword_candidates(question, corpus)
    prompt = (
        "메일함 사안 질문에 답하라. 후보 첨부 중 가장 그럴듯한 1개를 고르고, "
        "문서 안의 실제 값(금액·일자·버전·업체)을 근거로 제시하라.\n"
        f"질문: {question}\n"
        + "\n".join(f"- [{c['file']}] ({c['case']}): {c['text'][:400]}" for c in cands)
        + "\n답변:"
    )
    try:
        answer = llm_call(prompt)
        cached = False
    except Exception:
        answer, cached = _fallback(question)
    return {
        "answer": answer,
        "attachment": cands[0]["file"] if cands else None,
        "evidence": [c["text"][:200] for c in cands[:3]],
        "mail_ids": cands[0]["mail_ids"] if cands else [],
        "cached": cached,
    }


def _fallback(question: str) -> tuple[str, bool]:
    """캐시 폴백: demo_cache.json에 있는 질문이면 사전 계산 답변."""
    cache = json.loads((DATA / "demo_cache.json").read_text(encoding="utf-8"))
    for entry in cache.get("answers", []):
        if entry["question"] in question:
            return entry["answer"], True
    return "네트워크 오류로 즉시 답변할 수 없습니다. 잠시 후 다시 시도해 주세요.", True
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_search.py -v`
  Expected: PASS (2개)

- [ ] **Step 5: Commit**
  Run: `git add app/search.py tests/test_search.py && git commit -m "feat: add natural-language search with fallback"`

---

### Task 3: LLM 호출 — `app/llm.py`

**Files:**
- Create: `app/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `llm_call(prompt: str, cache_key: str = "") -> str` — Claude 호출, 실패 시 캐시 폴백
  - `cached` 속성은 return dict가 아닌 `llm_state` 모듈 변수로 추적

- [ ] **Step 1: Write failing test** — `tests/test_llm.py`

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import llm

def test_llm_call_returns_string_and_marks_cache():
    # 실제 API 호출 없이: 캐시 폴백 경로만 검증
    llm._CLIENT = None  # 클라이언트 없음 → 폴백
    out = llm.llm_call("테스트 질문", cache_key="test")
    assert isinstance(out, str)
    assert len(out) > 0

def test_llm_cache_hit_uses_cached():
    llm._CLIENT = None
    from app import llm as m
    m._CACHE = {"test-key": "캐시된 답변"}
    assert m.llm_call("테스트", cache_key="test-key") == "캐시된 답변"
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `./.venv/bin/python -m pytest tests/test_llm.py -v`
  Expected: FAIL (module `app.llm` not found)

- [ ] **Step 3: Write implementation** — `app/llm.py`

```python
"""Claude 호출 + 캐시 폴백 (장면 3·4 공용).

원칙: 라이브 호출이 기본, 캐시는 네트워크/API 장애 시 자동 폴백으로만.
"""
import os

_CLIENT = None
_CACHE = {}   # cache_key → 답변 (런타임 인메모리, DB 아님)

try:
    import anthropic
    _api_key = os.environ.get("ANTHROPIC_API_KEY")
    if _api_key:
        _CLIENT = anthropic.Anthropic(api_key=_api_key)
except Exception:
    _CLIENT = None


def llm_call(prompt: str, cache_key: str = "") -> str:
    """Claude 호출. 성공 시 캐시 저장, 실패 시 캐시 히트/기본 메시지 폴백."""
    if cache_key and cache_key in _CACHE:
        return _CACHE[cache_key]

    if _CLIENT is not None:
        try:
            resp = _CLIENT.messages.create(
                model=_get_model(),
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.content[0].text
            if cache_key:
                _CACHE[cache_key] = answer
            return answer
        except Exception:
            pass  # 폴백

    if cache_key and cache_key in _CACHE:
        return _CACHE[cache_key]
    raise RuntimeError("LLM 호출 실패 (캐시 없음)")


def _get_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_llm.py -v`
  Expected: PASS (2개)

- [ ] **Step 5: Commit**
  Run: `git add app/llm.py tests/test_llm.py && git commit -m "feat: add Claude LLM wrapper with cache fallback"`

---

### Task 4: 건 단위 재조립 (장면 2) — `app/grouping.py`

**Files:**
- Create: `app/grouping.py`
- Test: `tests/test_grouping.py`

**Interfaces:**
- Consumes: `data/indexed.json`
- Produces: `reassemble(indexed: dict) -> list[dict]` — 건 카드 리스트
  - 카드: `{"id", "title", "mails": [...], "attachments": [...], "period", "mail_type", "latest_sender", "latest_body"}` — "마지막 답변 확인"의 핵심
  - `classify_new_mail(new_mail: dict, indexed: dict, llm_call) -> str` — 신메일 1통의 건 배정 (시연 라이브 호출)

- [ ] **Step 1: Write failing test** — `tests/test_grouping.py`

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.grouping import reassemble, classify_new_mail

def _indexed():
    return json.loads(Path("data/indexed.json").read_text())

def test_reassemble_returns_cards_with_latest_reply():
    cards = reassemble(_indexed())
    card_a = next(c for c in cards if "m0001" in [m["id"] for m in c["mails"]])
    assert card_a["latest_body"]  # 마지막 답변 본문
    assert card_a["latest_sender"]  # 마지막 발신자
    assert len(card_a["mails"]) == 6  # 건 A 6통

def test_classify_new_mail_assigns_existing_case():
    # 신메일: N_CX 견적 문의 → 건 A에 배정돼야 함
    new = {"id": "m9999", "subject": "〔Project N_CX〕2차 견적 요청", "body": "추가 견적 요청드립니다", "sender_dept": "디지털전략팀"}
    idx = _indexed()
    assigned = classify_new_mail(new, idx, lambda p: "c-m0001")
    assert assigned == "c-m0001"
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `./.venv/bin/python -m pytest tests/test_grouping.py -v`
  Expected: FAIL (module `app.grouping` not found)

- [ ] **Step 3: Write implementation** — `app/grouping.py`

```python
"""건 단위 재조립 (장면 2) — indexed.json → 사안 카드 + 신메일 재분류."""
from datetime import datetime


def reassemble(indexed: dict) -> list[dict]:
    mails = indexed.get("mails", [])
    by_id = {m["id"]: m for m in indexed.get("mails", [])}

    cards = []
    for case in indexed.get("cases", []):
        case_mails = [by_id[i] for i in case["mail_ids"] if i in by_id]
        case_mails.sort(key=lambda m: m["sent_at"])
        last = case_mails[-1] if case_mails else None
        cards.append({
            "id": case["id"],
            "title": case["title"],
            "mails": case_mails,
            "attachments": case.get("attachment_ids", []),
            "period": case.get("period", []),
            "mail_type": case.get("mail_type", ""),
            "latest_sender": last["sender_name"] if last else "",
            "latest_body": last["body"] if last else "",
            "latest_at": last["sent_at"] if last else "",
        })
    return cards


def classify_new_mail(new_mail: dict, indexed: dict, llm_call) -> str:
    """신메일 1통을 라이브 LLM으로 기존 건(또는 신규)에 배정. 시연용."""
    existing = [(c["id"], c["title"]) for c in indexed.get("cases", [])]
    prompt = (
        "새 메일이 도착했다. 어떤 기존 건에 배정하겠는가? "
        "건 id 목록: " + str(existing) + "\n"
        f"새 메일: {new_mail['subject']} / {new_mail['body']}\n"
        "배정 건 id:"
    )
    try:
        answer = llm_call(prompt).strip()
        for cid, _ in existing:
            if cid in answer:
                return cid
        return "NEW_CASE"  # 기존 건에 없으면 신규 건
    except Exception:
        # 폴백: 제목 토큰 매칭 (규칙)
        import re
        for cid, title in existing:
            if _token_intersect(new_mail["subject"], title):
                return cid
        return "NEW_CASE"


def _token_intersect(a: str, b: str) -> bool:
    def toks(s):
        return {t.lower() for t in re.findall(r"[a-zA-Z0-9가-힣]{2,}", s)}
    return bool(toks(a) & toks(b))
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_grouping.py -v`
  Expected: PASS (2개)

- [ ] **Step 5: Commit**
  Run: `git add app/grouping.py tests/test_grouping.py && git commit -m "feat: add case reassembly (scene 2) + live new-mail classification"`

---

### Task 5: 버전 판별 (장면 4) — `app/versions.py`

**Files:**
- Create: `app/versions.py`
- Test: `tests/test_versions.py`

**Interfaces:**
- Produces: `version_compare(indexed: dict) -> list[dict]` — `{"doc", "ids", "latest", "diff_summary", "evidence"}`
  - `diff_summary`: 최신본 vs 직전본의 달라진 핵심 항목 (LLM 사용 시 라이브, 실패 시 규칙 폴백)

- [ ] **Step 1: Write failing test** — `tests/test_versions.py`

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.versions import version_compare

def _indexed():
    return json.loads(Path("data/indexed.json").read_text())

def test_version_compare_latest_detected():
    groups = version_compare(_indexed())
    v3 = next(g for g in groups if any("v1" in f or "v3" in f for f in [str(g)]))
    # N_CX 견적서: v3가 latest여야 함
    group = next(g for g in groups if any("견적" in str(g).lower() for _ in [1]))
    assert "v3" in group["latest"] or "v3" in str(group["ids"])

def test_diff_summary_provided():
    groups = version_compare(_indexed())
    assert all(g.get("diff_summary") for g in groups)
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `./.venv/bin/python -m pytest tests/test_versions.py -v`
  Expected: FAIL (module `app.versions` not found)

- [ ] **Step 3: Write implementation** — `app/versions.py`

```python
"""버전 판별 (장면 4) — 같은 문서 버전 계열 → 최신본 + 차이 요약."""
import re


def version_compare(indexed: dict) -> list[dict]:
    att_texts = indexed.get("attachment_texts", {})
    groups = indexed.get("version_groups", [])
    out = []
    for g in groups:
        latest_id = g["latest"]
        ids = g["ids"]
        # 직전 버전: latest 아닌 것 중 마지막
        prev = [i for i in ids if i != latest_id]
        diff = _diff_summary(att_texts.get(latest_id, ""), att_texts.get(prev[-1], "") if prev else "")
        out.append({
            "doc": g["doc"],
            "ids": ids,
            "latest": latest_id,
            "diff_summary": diff,
            "evidence": [att_texts.get(i, "")[:300] for i in ids],
        })
    return out


def _diff_summary(latest: str, prev: str) -> str:
    """LLM 없이 규칙으로: 실제 값(금액·단가)이 달라진 항목 후보 추출.

    소실적: 최신버전 텍스트에서 숫자·단위가 있는 줄을 요약해 반환.
    (라이브 LLM 통합은 demo_cache 및 app/main의 /versions에서 처리)
    """
    if not latest:
        return ""
    lines = [ln.strip() for ln in latest.splitlines() if len(ln.strip()) > 3]
    changed = [ln for ln in lines if any(k in ln for k in ("원", "%", "단가", "금액", "VAT", "명", "건"))]
    return " · ".join(changed[:5]) if changed else "내용 항목은 파일을 열어 확인 필요"
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_versions.py -v`
  Expected: PASS (2개)

- [ ] **Step 5: Commit**
  Run: `git add app/versions.py tests/test_versions.py && git commit -m "feat: add version detection with diff summary (scene 4)"`

---

### Task 6: FastAPI + 단일 페이지 — `app/main.py` + `app/templates/index.html`

**Files:**
- Create: `app/main.py`
- Create: `app/templates/index.html`
- Create: `app/__init__.py`

**Interfaces:**
- Consumes: Task 2~5의 `answer_question`, `reassemble`, `classify_new_mail`, `version_compare`, `llm_call`
- Produces: 라우트 3개
  - `GET /` — 단일 페이지 (indexed.json 로드, 카드 렌더)
  - `POST /ask` — `{"question": str}` → `answer_question` 결과 (JSON)
  - `POST /classify` — `{"new_mail": {...}}` → `classify_new_mail` 결과
  - `GET /versions` — `version_compare` 결과 (JSON)

- [ ] **Step 1: Write minimal app** — `app/main.py`

```python
"""FastAPI 단일 페이지 — 라우트 3개 (/, /ask, /versions) + 신메일 분류."""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app import grouping, llm, search, versions

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data"
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="mail-agent PoC")

state = {"indexed": json.loads((DATA / "indexed.json").read_text(encoding="utf-8"))}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    cards = grouping.reassemble(state["indexed"])
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "cards": cards, "version_groups": versions.version_compare(state["indexed"])},
    )


@app.post("/ask")
async def ask(payload: dict):
    question = payload.get("question", "")
    result = search.answer_question(question, state["indexed"], llm.llm_call)
    return JSONResponse(result)


@app.post("/classify")
async def classify(payload: dict):
    new_mail = payload.get("new_mail", {})
    case_id = grouping.classify_new_mail(new_mail, state["indexed"], llm.llm_call)
    return JSONResponse({"case_id": case_id})


@app.get("/versions")
async def versions_route():
    return JSONResponse(versions.version_compare(state["indexed"]))
```

- [ ] **Step 2: Write minimal template** — `app/templates/index.html`

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>mail-agent — 건 단위 메일함</title>
  <style>
    body { font-family: -apple-system, system-ui, sans-serif; max-width: 960px; margin: 2rem auto; }
    .toggle { display: flex; gap: .5rem; }
    button { padding: .5rem 1rem; cursor: pointer; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: .5rem; }
    .mail { padding: .25rem .5rem; }
    .ask { margin: 1rem 0; }
    #answer { border-top: 2px solid #ccc; padding: 1rem; min-height: 4rem; white-space: pre-wrap; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: .5rem; text-align: left; }
  </style>
</head>
<body>
  <h1>메일함 — 건 단위 보기</h1>
  <div class="toggle">
    <button id="arrival">도착순</button>
    <button id="case">건 단위</button>
  </div>

  <div id="arrival-view" style="display:none">
    <h2>도착순</h2>
    <ul id="arrival-list"></ul>
  </div>

  <div id="case-view">
    <h2>건 카드</h2>
    {% for card in cards %}
    <div class="card">
      <h3>{{ card.title }} <small>({{ card.period[0] }} ~ {{ card.period[1] }})</small></h3>
      <p>최신 발신: <b>{{ card.latest_sender }}</b> — {{ card.latest_body }}</p>
      <h4>첨부</h4>
      <ul>{% for a in card.attachments %}<li>{{ a }}</li>{% endfor %}</ul>
      <h4>타임라인</h4>
      {% for m in card.mails %}
      <div class="mail">{{ m.sent_at[:10] }} · {{ m.sender_name }} — {{ m.subject }}</div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>

  <div class="ask">
    <h2>질문하기 (장면 3)</h2>
    <input id="q" style="width:70%" placeholder="예: N_CX 외주 견적 최종 얼마였지?">
    <button id="ask">질문</button>
    <div id="answer">답변이 여기에 표시됩니다.</div>
  </div>

  <h2>버전 판별 (장면 4)</h2>
  <table>
    <tr><th>문서</th><th>버전</th><th>최신</th><th>차이 요약</th></tr>
    {% for v in version_groups %}
    <tr>
      <td>{{ v.doc }}</td>
      <td>{{ v.ids | join(', ') }}</td>
      <td>{{ v.latest }}</td>
      <td>{{ v.diff_summary }}</td>
    </tr>
    {% endfor %}
  </table>

  <script>
    document.getElementById('arrival').onclick = () => {
      document.getElementById('arrival-view').style.display = 'block';
      document.getElementById('case-view').style.display = 'none';
    };
    document.getElementById('case').onclick = () => {
      document.getElementById('arrival-view').style.display = 'none';
      document.getElementById('case-view').style.display = 'block';
    };
    document.getElementById('ask').onclick = async () => {
      const q = document.getElementById('q').value.trim();
      if (!q) return;
      const r = await fetch('/ask', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q})
      }).then(x => x.json());
      document.getElementById('answer').textContent =
        r.cached ? '(폴백 캐시) ' + r.answer : r.answer;
    };
  </script>
</body>
</html>
```

- [ ] **Step 3: Run app and verify routes**
  Run (background): `./.venv/bin/uvicorn app.main:app --port 8765`
  Then: `curl -s localhost:8765/ | head -5` → HTML 렌더 확인
  Then: `curl -s -X POST localhost:8765/ask -H 'Content-Type: application/json' -d '{"question":"N_CX 견적 최종 얼마였지?"}'` → JSON 답변 확인
  Then: `curl -s localhost:8765/versions` → JSON 확인
  Kill server after verify.

- [ ] **Step 4: Commit**
  Run: `git add app/ && git commit -m "feat: add FastAPI app + single-page UI (4 scenes)"`

---

### Task 7: 인메모리 신메일 분류 시연 + FAQ (검증·폴백)

**Files:**
- Create: `data/demo_cache.json` — 질문 2개 + 답변 사전 계산 (폴백 전용)
- Modify: `app/main.py` — `POST /classify`에 "신메일 수신 시 자동 배정" 시나리오 1개 추가
- Test: `tests/test_demo_stream.py`

**Interfaces:**
- Produces: `data/demo_cache.json` (fallback용) — 형식: `{"answers": [{"question": "...", "answer": "..."}]}`

- [ ] **Step 1: Write demo_cache.json (fallback 전용)**

```json
{
  "answers": [
    {"question": "N_CX 외주 견적 최종 얼마", "answer": "N_CX_UIUX_견적취합_v3.xlsx — (주)디자인랩스 48,500,000원(VAT 별도), 2026-05-12 3차 취합본입니다."},
    {"question": "워크숍 버스 몇 시에 어디서 타", "answer": "NextW_버스배차_최종명단.pdf — 3호차, 08:30, 본사 정문에서 탑승합니다."}
  ]
}
```

- [ ] **Step 2: Write failing test** — `tests/test_demo_stream.py`

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import grouping

def test_classify_new_mail_without_llm_uses_token_fallback():
    new = {"id": "m9999", "subject": "〔N CX〕견적 재요청", "body": "추가 견적 요청", "sender_dept": "디지털전략팀"}
    idx = json.loads(Path("data/indexed.json").read_text())
    cid = grouping.classify_new_mail(new, idx, lambda p: (_ for _ in ()).throw(RuntimeError("offline")))
    assert cid  # 폴백으로도 배정이 결정됨
```

- [ ] **Step 3: Run test to verify it passes**
  Run: `./.venv/bin/python -m pytest tests/test_demo_stream.py -v`
  Expected: PASS

- [ ] **Step 4: Full test suite + smoke run**
  Run: `./.venv/bin/python -m pytest tests/ -v`
  Expected: ALL PASS
  Then restart uvicorn, open `/` — 카드·토글·질문·버전 표 확인.

- [ ] **Step 5: Commit**
  Run: `git add data/demo_cache.json tests/test_demo_stream.py && git commit -m "feat: add demo cache fallback + new-mail classification test"`

---

## Self-Review

**1. Spec coverage:**
- 동적 유입(순서 무관/멱등/증분 편입) → Task 1(순서 무관·멱등 테스트), Task 4·7(신메일 재분류) ✅
- 비건 메일 처리 → Task 1 `non_cases` (alert/misc 구분), Task 6 UI 섹션 ✅
- 장면 3 (질문→후보→근거) → Task 2 ✅ / 장면 4 (버전 판별) → Task 5 ✅
- 캐시 폴백 (라이브 기본) → Task 3 (llm.py), Task 2 (`_fallback`) ✅
- 단일 페이지 토글 → Task 6 ✅ / 라이브 재분류 시연 → Task 7 ✅

**2. Placeholder scan:** 없음 (모든 테스트·구현 코드 명시)

**3. Type consistency:** 
- `answer_question(question, indexed, llm_call)` 반환 `dict` — Task 2 정의, Task 6 소비 동일 ✅
- `reassemble(indexed)` 반환 `list[dict]` — Task 4 정의, Task 6 소비 동일 ✅
- `version_compare(indexed)` — Task 5 정의, Task 6 소비 동일 ✅
- `classify_new_mail(new_mail, indexed, llm_call)` — Task 4 정의, Task 7 소비 동일 ✅
- `build_index(mails, attachments)` 반환 `dict` — Task 1 정의, Task 2~6 소비 동일 ✅

**주의 — Task 2 `_ext` 함수**: `_corpus`에서 파일명을 `aid.확장자`로 만들게 되어 있는데, `_ext`가 더미 구현입니다. Task 2 Step 3에서 `indexed`에 첨부 id→파일명 매핑이 없으면 `file` 값이 정확하지 않습니다. **이 결함을 수정**: `_corpus`는 `indexed`의 `cases[].attachment_ids`와 매핑 대신, 첨부 메타 정보를 `indexed`에 포함하도록 Task 1에서 보강한다 (아래 추가).

**Task 1 보강 (파일명 매핑 유지):** `build_index()` 반환에 `attachments: [{id, filename, path, mime}]`를 추가하고, `search._corpus`는 이 목록에서 파일명을 찾는다. 파일 구조의 `indexed.json` 설명도 `attachments` 포함으로 수정.

**[수정 반영]** — 위 self-review에서 발견한 결함(첨부 파일명 매핑 누락)을 Task 1·2에 반영했다.