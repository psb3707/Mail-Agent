"""자연어 질의 → 건·첨부 후보 축소 → 근거 추출 → LLM 답변 (장면 3).

라이브 LLM 호출이 기본. 실패 시 인메모리 폴백(사전 계산 정답)으로 처리.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# 인메모리 폴백용 사전 계산 정답 (지시 004: demo_cache.json은 D1-7에서 생성 예정)
_FALLBACK_ANSWERS = [
    {
        "question": "N_CX 외주 견적 최종 얼마",
        "answer": "N_CX_UIUX_견적취합_v3.xlsx — (주)디자인랩스 48,500,000원(VAT 별도), 2026-05-12 3차 취합본입니다.",
        "attachment": "N_CX_UIUX_견적취합_v3.xlsx",
    },
    {
        "question": "워크숍 버스 몇 시에 어디서 타",
        "answer": "NextW_버스배차_최종명단.pdf — 3호차, 08:30, 본사 정문에서 탑승합니다.",
        "attachment": "NextW_버스배차_최종명단.pdf",
    },
]


def _corpus(indexed: dict) -> list[dict]:
    """후보 첨부: 추출 텍스트 + 소속 건 + 파일명을 묶은 서치 코퍼스."""
    att_meta = {a["id"]: a for a in indexed.get("attachments", [])}
    att_texts = indexed.get("attachment_texts", {})
    out = []
    for case in indexed.get("cases", []):
        for aid in case.get("attachment_ids", []):
            meta = att_meta.get(aid, {})
            out.append({
                "file": meta.get("filename", aid),
                "text": att_texts.get(aid, ""),
                "case": case["title"],
                "mail_ids": case["mail_ids"],
            })
    return out


def _keyword_candidates(question: str, corpus: list[dict], top_k: int = 6) -> list[dict]:
    """질문 키워드(한글·영문 토큰)와 코퍼스 텍스트·건 제목의 교집합으로 후보 축소."""
    toks = set(question.lower().split())
    scored = []
    for item in corpus:
        score = 0
        for t in toks:
            if t in item["text"].lower() or t in item["case"].lower():
                score += 1
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored][:top_k] or corpus[:top_k]


def _fallback(question: str) -> dict:
    """캐시 폴백: data/demo_cache.json(지시-007)을 읽어 정답을 찾는다.

    - 파일이 없거나 질문이 매치 안 되면 기본 메시지로 폴백.
    - 라이브 LLM이 기본 경로이며, 이 함수는 네트워크/API 장애 시에만 호출된다.
    """
    answers = _FALLBACK_ANSWERS
    cache_path = DATA / "demo_cache.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        file_answers = cached.get("answers", [])
        if file_answers:
            answers = file_answers
    except Exception:
        pass  # 파일 없음/손상 → 하드코딩 폴백

    for entry in answers:
        if entry.get("question", "") in question:
            return {
                "answer": entry.get("answer", ""),
                "attachment": entry.get("attachment", None),
                "evidence": entry.get("evidence", []),
                "mail_ids": [],
                "cached": True,
            }
    return {
        "answer": "네트워크 오류로 즉시 답변할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        "attachment": None,
        "evidence": [],
        "mail_ids": [],
        "cached": True,
    }


def _evidence_lines(text: str, limit: int = 3) -> list[str]:
    """문서 텍스트에서 실제 값(금액·단위·일자·업체명)이 있는 줄을 우선 근거로 추출."""
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 1]
    # 실제 값 우선순위: 숫자(금액·호차·인원) 또는 업체명(주)·날짜가 있는 줄
    def _score(ln: str) -> int:
        s = 0
        if any(ch.isdigit() for ch in ln):
            s += 3
        if any(k in ln for k in ("주)", "원", "호차", "출발", "집결", "작성일", "선정")):
            s += 5
        return s
    scored = sorted(lines, key=_score, reverse=True)
    return scored[:limit]


def _find_attachment_in_answer(answer: str, corpus: list[dict]) -> dict | None:
    """LLM 답변에서 언급된 첨부 파일명을 코퍼스에서 찾는다.

    answer_question은 LLM 답변을 그대로 answer로 쓰므로, LLM이 '이 첨부가 정답'이라
    답했다면 attachment·evidence도 그 첨부 기준으로 갱신해야 '왜 이것인가'가 성립한다.
    """
    if not answer:
        return None
    for item in corpus:
        if item["file"] in answer:
            return item
    return None


def answer_question(question: str, indexed: dict, llm_call) -> dict:
    """자연어 질문 → 정답 첨부 + '왜 이것인가' 근거 (장면 3)."""
    corpus = _corpus(indexed)
    cands = _keyword_candidates(question, corpus)

    prompt = (
        "메일함 사안 질문에 답하라. 후보 첨부 중 가장 그럴듯한 1개를 고르고, "
        "문서 안의 실제 값(금액·일자·버전·업체)을 근거로 제시하라. "
        "'왜 이것인가'를 반드시 포함하라.\n"
        f"질문: {question}\n"
        + "\n".join(f"- [{c['file']}] ({c['case']}): {c['text'][:500]}" for c in cands)
        + "\n답변:"
    )
    try:
        answer = llm_call(prompt)
        cached = False
    except Exception:
        return _fallback(question)

    chosen = _find_attachment_in_answer(answer, corpus) or (cands[0] if cands else None)
    return {
        "answer": answer,
        "attachment": chosen["file"] if chosen else None,
        "evidence": _evidence_lines(chosen["text"]) if chosen else [],
        "mail_ids": chosen["mail_ids"] if chosen else [],
        "cached": cached,
    }