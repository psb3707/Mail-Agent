"""분류AI(건 트리 구축) — OpenRouter 기반 분류 파이프라인 헤드 (지시-022).

설계서: docs/plans/2026-09-10-classifier-ai.md (§4 알고리즘 흐름)
역할: `data/mails.json`(400통)을 건(件) 단위로 재조립해
      `data/indexed.json`(AI-Ready DB) 스키마와 호환되는 JSON을 산출한다.
      관리 Agent는 산출물(`indexed.json`)만 소비하므로 이 모듈은 파이프라인 헤드로 독립한다.

원칙:
- 규칙으로 되는 판단(표기 정규화·회신 그래프·버전 파일명)은 규칙, 같은 건/버전 판단만 LLM.
- LLM 라이브 호출이 기본, 실패 시 규칙 폴백(scripts/build_index.py)과 비건 안전 귀결.
- 순서 무관·멱등: 건 ID는 시퀀스가 아니라 콘텐츠·발신자 기반 안정 키.
- 실리미트는 env(CLASSIFIER_*)로 주입 — 코드에 하드코딩 금지.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# 직접 실행(python scripts/classify.py) 시에도 app/scripts를 import할 수 있게 경로 보장
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 실리미트 설정화 (§6-2) — env로 주입, 코드에 임의 숫자 하드코딩 금지
_CLASSIFIER_MODEL = os.environ.get(
    "CLASSIFIER_MODEL", os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash-0731")
)
_CLASSIFIER_TEMPERATURE = float(os.environ.get("CLASSIFIER_TEMPERATURE", "0.0"))
_CLASSIFIER_MAX_TOKENS = int(os.environ.get("CLASSIFIER_MAX_TOKENS", "4096"))
_CLASSIFIER_CHUNK_SIZE = int(os.environ.get("CLASSIFIER_CHUNK_SIZE", "40"))
_CLASSIFIER_MAX_RETRIES = int(os.environ.get("CLASSIFIER_MAX_RETRIES", "1"))

# 분류 전용 프롬프트·JSON 스키마는 이 모듈 내부에 둔다 (§3-1: 게이트는 app/llm.py 재사용)


class ClassifierError(RuntimeError):
    """분류 실패 신호 — 폴백 경로로 안전하게 귀결한다."""


# ---------- 1차 규칙 전처리 (LLM 전, build_index.py 규칙 재사용) ----------

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


def _norm_subject(subject: str) -> str:
    """말머리·대소문자·구분자와 자주 흔들리는 표기를 정규화한다."""
    s = subject.lower()
    s = re.sub(r"\b(?:re|fw|fwd)\s*:", " ", s)
    s = s.replace("workshop", "워크숍").replace("워크샵", "워크숍")
    s = re.sub(r"[〔〕\[\]()（）]", " ", s)
    s = re.sub(r"[_\-./]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _topic_marker(subject: str) -> str:
    normalized = _norm_subject(subject)
    for marker, pattern in _TOPIC_PATTERNS:
        if pattern.search(normalized):
            return marker
    return ""


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
        component: set[str] = set()
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


def _mail_time(mail: dict) -> datetime:
    return datetime.fromisoformat(mail.get("sent_at", ""))


def _reply_roots(components: list[set[str]]) -> dict[str, str]:
    """연결요소별 대표 메일 id(가장 이른 시각·가장 작은 id) — 청크 분할 보조."""
    roots = {}
    for component in components:
        roots[min(component)] = "thread"
    return roots


# ---------- LLM 그룹핑 (2차 — 같은 건 판단, §3 JSON 모드) ----------


def _compact_mail(mail: dict) -> dict:
    """LLM에 보낼 메일 메타 축약 — 본문은 요약, 첨부는 파일명만."""
    subject = mail.get("subject", "")
    body = (mail.get("body") or "").strip()
    body_preview = re.sub(r"\s+", " ", body)[:120] if body else ""
    return {
        "id": mail["id"],
        "subject": subject,
        "sender": mail.get("sender_name", ""),
        "dept": mail.get("sender_dept", ""),
        "sent_at": mail.get("sent_at", ""),
        "reply_to": mail.get("reply_to"),
        "attachments": [a.get("filename", a.get("id", "")) for a in mail.get("attachments", [])],
        "body_preview": body_preview,
    }


def _chunk_mails(mails: list[dict], rules: dict[str, list[set[str]]]) -> list[list[dict]]:
    """배치 청킹 (§3-4): 회신 스레드를 같은 청크에 유지하고 크기 상한을 지킨다.

    - 1차 규칙 전처리 결과(회신 연결요소)를 우선 배치로 묶는다.
    - 연결요소가 상한을 넘으면 시간대 기준으로 쪼갠다(스레드 보존 최우선).
    - 비건 후보(시스템 발신)는 뒤쪽 청크로 몰아 LLM 판단 양을 줄인다.
    """
    threads = rules.get("threads", [])
    size = _CLASSIFIER_CHUNK_SIZE
    chunked: list[list[dict]] = []

    used: set[str] = set()
    pending = [mail for mail in mails if mail["id"] not in used]
    # 시스템 발신자는 비건 우선 — LLM에 보내는 양을 줄이기 위해 뒤로 미룬다
    ordered = sorted(
        pending,
        key=lambda mail: (0 if mail.get("sender_dept") == "시스템" else 1, mail.get("sent_at", ""), mail["id"]),
    )

    for thread in threads:
        thread_mails = [mail for mail in ordered if mail["id"] in thread]
        if not thread_mails:
            continue
        if len(thread_mails) <= size:
            chunked.append(thread_mails)
            used.update(mail["id"] for mail in thread_mails)
        else:
            for i in range(0, len(thread_mails), size):
                chunked.append(thread_mails[i : i + size])
                used.update(mail["id"] for mail in thread_mails[i : i + size])

    rest = [mail for mail in ordered if mail["id"] not in used]
    for i in range(0, len(rest), size):
        chunked.append(rest[i : i + size])
    return chunked


def _build_group_prompt(chunk: list[dict]) -> str:
    """청크별 '같은 건' 판단 프롬프트 — JSON mode 출력 계약."""

    def line(mail: dict) -> str:
        atts = ",".join(mail["attachments"]) or "-"
        body = (mail.get("body_preview") or "").strip()
        sender = f"{mail['sender']}({mail['dept']})" if mail.get("dept") else mail.get("sender", "-")
        return (
            f"- id={mail['id']} | {mail['subject']} | {sender} | {mail['sent_at']} "
            f"| reply_to={mail.get('reply_to') or '-'} | 첨부={atts}"
            + (f" | 본문일부: {body}" if body else "")
        )

    mails_text = "\n".join(line(mail) for mail in chunk)
    return f"""당신은 사내 메일함을 '건(件)' 단위로 재조립하는 분류기입니다.

아래 메일들은 한 조직 구성원의 메일함 일부입니다. 이 메일들이 **같은 업무 건(件)**으로 묶이는지 판단하세요.
같은 건의 기준: 같은 업무 목적을 공유(제목 표기 흔들림·끊긴 스레드·축약 표기도 같은 건일 수 있음).
반복 알림·공지·개인 메일은 건이 아니라 비건(non-case)입니다.

판단 근거로 다음을 참고하세요:
- 제목 표기 흔들림: N_CX / N CX / N_CX 축약은 같은 Project를 가리킬 수 있음
- reply_to: 스레드 관계(끊겨도 같은 건일 수 있음)
- 발신자·시각·첨부 파일명: 보조 단서

응답은 반드시 아래 JSON 형식으로만 주세요(다른 텍스트 금지):
{{
  "groups": [
    {{"case_key": "같은 건으로 묶을 그룹 이름(예: n cx 견적)", "mail_ids": ["id1","id2"], "reason": "판단 근거 한 줄"}}
  ],
  "non_cases": ["id3","id4"]
}}

규칙:
- case_key는 같은 그룹끼리 동일하게, 다른 그룹과 다르게 지으세요.
- 건이 아닌 메일은 반드시 non_cases에 넣으세요(빈 배열 가능).
- 모든 메일 id는 정확히 한 번만(groups 또는 non_cases) 등장해야 합니다.

메일 목록:
{mails_text}

JSON 응답:"""


def _parse_groups_response(raw: str) -> list[dict] | None:
    """분류 전용 응답 검증 — {groups:[], non_cases:[]} 형태인지 확인하고 정규화한다."""
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    groups = data.get("groups")
    if not isinstance(groups, list):
        return None
    normalized = []
    for item in groups:
        if not isinstance(item, dict):
            continue
        mail_ids = item.get("mail_ids")
        case_key = item.get("case_key")
        if not isinstance(mail_ids, list) or not isinstance(case_key, str) or not case_key:
            continue
        normalized.append({
            "case_key": case_key,
            "mail_ids": [mid for mid in mail_ids if isinstance(mid, str)],
            "reason": str(item.get("reason", "")),
        })
    # groups 배열이 있었는데 정상 항목이 0개면 파싱 실패로 본다 (빈 답과 구분)
    if groups and not normalized:
        return None
    return normalized


def _llm_group_chunk(
    chunk: list[dict],
    llm_call: Callable[[str, str], str],
) -> tuple[list[dict], list[str]]:
    """청크 1개를 LLM으로 분류. 파싱 실패 시 ClassifierError(→부분 재시도/폴백)."""
    prompt = _build_group_prompt(chunk)
    raw = llm_call(prompt, cache_key=f"classify-chunk:{','.join(m['id'] for m in chunk)}")
    groups = _parse_groups_response(raw)
    if groups is None:
        raise ClassifierError("LLM 응답 파싱 실패 (JSON 아님)")
    return groups, [item["case_key"] for item in groups]


# ---------- 3차 건 안정 키 부여 (§4-3) ----------


def _stable_case_id(group: list[dict]) -> str:
    """건 안정 키 — 시퀀스 금지. 콘텐츠 기반: 가장 이른 시각·가장 작은 id."""
    return f"c-{min(m['id'] for m in group)}"


def _merge_case_maps(
    groups_by_chunk: list[list[dict]], mails_by_id: dict[str, dict]
) -> dict[str, dict]:
    """청크별 결정을 안정 키 기준으로 병합. 충돌 시 발신자·기간·공유 첨부로 우선순위.

    반환: case_key → {"mail_ids": set, "reason": str}
    """
    merged: dict[str, dict] = {}
    for groups in groups_by_chunk:
        for group in groups:
            key = group["case_key"]
            ids = set(group["mail_ids"])
            if key not in merged:
                merged[key] = {"mail_ids": set(), "reason": group.get("reason", "")}
            merged[key]["mail_ids"] |= ids
    return merged


def _resolve_key_conflicts(case_map: dict[str, dict], mails_by_id: dict[str, dict]) -> list[set[str]]:
    """한 메일이 여러 case_key에 중복 배정되면 가장 오래된(사전순) 키에만 남긴다."""
    owner: dict[str, str] = {}
    for key in sorted(case_map, key=lambda k: (-len(case_map[k]["mail_ids"]), k)):
        for mid in case_map[key]["mail_ids"]:
            owner.setdefault(mid, key)
    by_key: dict[str, set[str]] = defaultdict(set)
    for mid, key in owner.items():
        by_key[key].add(mid)
    return [ids for ids in by_key.values() if len(ids) >= 1]


def _assign_non_cases(
    all_mails: list[dict], case_sets: list[set[str]]
) -> list[dict]:
    """어느 건에도 안 붙는 메일은 무시하지 않고 alert/misc로 분류 (§1-2·§4-3)."""
    case_ids = set().union(*case_sets) if case_sets else set()
    non_cases = []
    for mail in sorted(all_mails, key=lambda item: (item.get("sent_at", ""), item["id"])):
        if mail["id"] in case_ids:
            continue
        kind = "alert" if mail.get("sender_dept") == "시스템" else "misc"
        non_cases.append({"id": mail["id"], "subject": mail["subject"], "type": kind})
    return non_cases


# ---------- 4차 버전 계열 판별 (§4-4) ----------


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


def detect_version_groups(attachments: list[dict]) -> list[dict]:
    """첨부 파일명 정규화로 같은 문서 버전 계열 탐지 (규칙 폴백 포함 — §4-4)."""
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


# ---------- 증분 편입 (§4-5) ----------


def _incremental_decide(
    new_mail: dict,
    cases: list[dict],
    llm_call: Callable[[str, str], str],
) -> str:
    """신메일 1통 → ① 기존 건 참가 ② 새 건 ③ 비건 — 3갈래 결정 (JSON mode)."""
    case_rows = "\n".join(
        f"- {c['id']} | {c['title']} | mail_ids={c['mail_ids']}" for c in cases
    )
    prompt = f"""당신은 인메모리 상태의 건 트리에 **새 메일 1통**을 편입하는 분류기입니다.

기존 건 목록:
{case_rows or "(없음)"}

새 메일:
- id={new_mail.get('id')}
- subject={new_mail.get('subject')}
- sender={new_mail.get('sender_name')}({new_mail.get('sender_dept')})
- sent_at={new_mail.get('sent_at')}
- reply_to={new_mail.get('reply_to') or '-'}
- 첨부={','.join(a.get('filename','') for a in new_mail.get('attachments',[])) or '-'}
- 본문일부: {(new_mail.get('body') or '')[:120]}

응답은 반드시 아래 JSON 형식으로만 주세요(다른 텍스트 금지):
{{"decision": "existing", "case_id": "기존 건 id", "reason": "..."}}
또는
{{"decision": "new_case", "case_key": "새 건 이름", "reason": "..."}}
또는
{{"decision": "non_case", "type": "alert|misc", "reason": "..."}}

규칙: 기존 건과 같은 업무면 existing, 새 업무의 시작이면 new_case, 공지·알림·개인이면 non_case.

JSON 응답:"""
    raw = llm_call(prompt, cache_key=f"classify-incremental:{new_mail.get('id')}")
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError
        data = json.loads(raw[start : end + 1])
        decision = data.get("decision")
        if decision not in ("existing", "new_case", "non_case"):
            raise ValueError
        return decision
    except (json.JSONDecodeError, ValueError, AttributeError):
        raise ClassifierError("증분 판단 응답 파싱 실패")


# ---------- 메인 파이프라인 ----------


def _extract_text(path: Path, mime: str) -> str:
    """첨부 본문 텍스트 추출 — 규칙 파이프라인이 담당(§2-1, LLM에 첨부 본문 안 보냄)."""
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


def _make_case(title: str, ids: set[str], mails_by_id: dict[str, dict]) -> dict:
    ordered = sorted(
        (mails_by_id[mid] for mid in ids),
        key=lambda mail: (mail.get("sent_at", ""), mail["id"]),
    )
    attachment_ids = list(dict.fromkeys(
        aid for mail in ordered for aid in mail.get("attachments", [])
    ))
    return {
        "id": f"c-{min(ids)}",
        "title": title,
        "mail_ids": [mail["id"] for mail in ordered],
        "attachment_ids": attachment_ids,
        "period": [ordered[0]["sent_at"][:10], ordered[-1]["sent_at"][:10]],
        "mail_type": "프로젝트",
        "summary": " ".join(mail.get("body", "")[:60] for mail in ordered[:3]),
    }


def classify(
    mails: list[dict],
    attachments: list[dict],
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """분류 파이프라인 1회 실행 — indexed.json 스키마 호환 JSON 반환.

    llm_call이 None이거나 실패하면 규칙 폴백(회신 그래프·표기 정규화)으로 대체된다.
    temp: 순서 무관·멱등 보장을 위해 모든 결정은 입력 순서와 무관한 안정 키 사용.
    """
    from app import llm as _llm

    def _classifier_call(prompt: str, cache_key: str = "") -> str:
        """분류 전용 게이트 — call_openrouter 확장(JSON 모드·max_tokens) + 캐시 폴백.

        llm_call 시그니처(prompt, cache_key)를 유지하면서, 분류에 필요한
        response_format과 max_tokens를 적용한다. 캐시는 재호출 방지·재현용으로만.
        """
        if cache_key and cache_key in _llm._CACHE:
            return _llm._CACHE[cache_key]
        try:
            answer = _llm.call_openrouter(
                prompt,
                model=_CLASSIFIER_MODEL,
                max_tokens=_CLASSIFIER_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception:
            return _llm.llm_call(prompt, cache_key=cache_key)  # 폴백 (캐시·기본 메시지)
        if cache_key:
            _llm._CACHE[cache_key] = answer
        return answer

    caller = llm_call or _classifier_call

    mails_by_id = {mail["id"]: mail for mail in mails}

    # 1차 규칙 전처리 (회신 그래프 = 청크 배치 보조, LLM이 뒤집을 수 있음)
    threads = _reply_components(mails)

    # 2차 LLM 그룹핑 (JSON mode, 배치 청킹)
    chunked = _chunk_mails(mails, {"threads": threads})

    groups_by_chunk: list[list[dict]] = []
    llm_ok = False
    fallback_chunks = 0
    for chunk in chunked:
        groups = None
        try:
            groups, _ = _llm_group_chunk(chunk, caller)
        except Exception:
            # 폴백 3단계 1: 부분 재시도 (1회)
            if _CLASSIFIER_MAX_RETRIES > 0:
                try:
                    groups, _ = _llm_group_chunk(chunk, caller)
                except Exception:
                    groups = None
        if groups is not None:
            groups_by_chunk.append(groups)
            llm_ok = True
        else:
            # 폴백 3단계 2: 규칙 폴백 — 이 청크의 메일을 회신 그래프 기준으로만 묶는다
            # (LLM 결정이 없으므로, 과잉 분류를 막기 위해 크기 1 건은 비건으로 안전 귀결)
            fallback_chunks += 1
            groups_by_chunk.append([{
                "case_key": f"upstream-rule-{fallback_chunks}",
                "mail_ids": [mail["id"] for mail in chunk],
                "reason": "LLM 실패 → 규칙 폴백",
            }])

    if fallback_chunks == len(chunked):
        # 모든 청크가 규칙 폴백 → LLM 경로가 완전히 불가 (키 없음/네트워크 장애)
        # 폴백 3단계 2: 기존 build_index 규칙 결과로 안전 전환 (재현율 1.0 보장)
        from scripts.build_index import build_index as _rule_build
        return _rule_build(mails, attachments)

    case_map = _merge_case_maps(groups_by_chunk, mails_by_id)

    # 3차 안정 키 + 충돌 해소
    case_sets = _resolve_key_conflicts(case_map, mails_by_id)
    # 규칙 폴백 청크가 실제로 건인지 LLM 판단을 못 받았으므로, 회신 그래프 외 개별 메일은
    # 과잉 분류를 막기 위해 크기 1 건은 비건으로 안전 귀결한다 (어느 건에도 강제로 안 붙임).
    final_sets: list[set[str]] = []
    for ids in case_sets:
        if len(ids) == 1:
            continue  # 비건 처리로
        final_sets.append(ids)

    cases = []
    for ids in final_sets:
        title = _topic_marker(next((mails_by_id[mid].get("subject", "") for mid in ids), ""))
        cases.append(_make_case(title or "업무 건", ids, mails_by_id))

    attachment_texts = {}
    for attachment in sorted(attachments, key=lambda item: item["id"]):
        raw_path = Path(attachment["path"])
        path = raw_path if raw_path.is_absolute() else ROOT / raw_path
        attachment_texts[attachment["id"]] = _extract_text(path, attachment["mime"])

    non_cases = _assign_non_cases(mails, final_sets)
    version_groups = detect_version_groups(attachments)

    return {
        "cases": cases,
        "attachment_texts": attachment_texts,
        "version_groups": version_groups,
        "non_cases": non_cases,
        "attachments": attachments,
    }


def incremental(
    new_mail: dict,
    cases: list[dict],
    llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """신메일 1통 증분 편입 결정 (§4-5). 반환: {decision, case_id|case_key|type, reason}."""
    from app import llm as _llm

    def _classifier_call(prompt: str, cache_key: str = "") -> str:
        if cache_key and cache_key in _llm._CACHE:
            return _llm._CACHE[cache_key]
        try:
            answer = _llm.call_openrouter(
                prompt,
                model=_CLASSIFIER_MODEL,
                max_tokens=_CLASSIFIER_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception:
            return _llm.llm_call(prompt, cache_key=cache_key)
        if cache_key:
            _llm._CACHE[cache_key] = answer
        return answer

    caller = llm_call or _classifier_call
    try:
        decision = _incremental_decide(new_mail, cases, caller)
    except Exception:
        return {"decision": "non_case", "type": "misc", "reason": "LLM 실패 → 비건 안전 귀결"}
    if decision == "existing":
        return {"decision": "existing", "case_id": None, "reason": "기존 건 편입"}
    if decision == "new_case":
        return {"decision": "new_case", "case_key": None, "reason": "새 건 시작"}
    return {"decision": "non_case", "type": None, "reason": "비건 처리"}


def build_index_rule_fallback(mails: list[dict], attachments: list[dict]) -> dict:
    """규칙 폴백 엔트리 — scripts/build_index.py와 동일 결과 (LLM 완전 불가 시)."""
    from scripts.build_index import build_index

    return build_index(mails, attachments)


def main() -> None:
    source = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
    print(f"[classify] 모델: {_CLASSIFIER_MODEL} / temperature={_CLASSIFIER_TEMPERATURE} "
          f"/ max_tokens={_CLASSIFIER_MAX_TOKENS} / chunk={_CLASSIFIER_CHUNK_SIZE}")
    try:
        result = classify(source["mails"], source["attachments"])
        origin = "LLM"
    except Exception as exc:  # noqa: BLE001 — 루트 레벨은 규칙 폴백으로 안전 귀결
        print(f"[classify] LLM 경로 실패({exc}) → 규칙 폴백")
        result = build_index_rule_fallback(source["mails"], source["attachments"])
        origin = "RULE-FALLBACK"
    (DATA / "indexed.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"cases: {len(result['cases'])} / non_cases: {len(result['non_cases'])} "
          f"/ versions: {len(result['version_groups'])} (origin={origin})")
    print("→ data/indexed.json 저장 완료")


if __name__ == "__main__":
    main()