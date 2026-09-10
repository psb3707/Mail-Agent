"""FastAPI 단일 페이지 — 라우트 4개 (/, /ask, /classify, /versions) (D1-6).

이 모듈은 **조합(composition)만 담당**한다:
- 각 기능은 `app/llm.py`·`app/grouping.py`·`app/search.py`·`app/versions.py`에 위임.
- 향후 분류AI·관리 Agent가 같은 레포의 별도 모듈로 붙을 수 있게 라우트 경계를 유지한다.

원칙:
- `data/indexed.json`은 읽기 전용 (원본 메일함 무수정).
- 저장은 인메모리 (DB 없음). 라이브 LLM 호출이 기본, 캐시는 폴백 전용.
"""
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

# 서버 시작 시 사전 계산 결과를 인메모리로 로드 (읽기 전용)
_indexed = json.loads((DATA / "indexed.json").read_text(encoding="utf-8"))

# 신메일 증분 편입 시연용 인메모리 상태 (영속화하지 않음)
state = {
    "indexed": _indexed,
    "new_mails": [],
}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    cards = grouping.reassemble(state["indexed"])
    version_rows = versions.version_compare(state["indexed"])
    non_cases = state["indexed"].get("non_cases", [])
    alerts = [n for n in non_cases if n.get("type") == "alert"]
    misc = [n for n in non_cases if n.get("type") != "alert"]
    # starlette 1.6.0 신형 시그니처: TemplateResponse(request, name, context)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "cards": cards,
            "version_rows": version_rows,
            "alerts": alerts,
            "misc": misc,
            "new_mails": state["new_mails"],
        },
    )


@app.post("/ask")
async def ask(payload: dict):
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(
            {"answer": "질문을 입력해 주세요.", "attachment": None,
             "evidence": [], "mail_ids": [], "cached": False}
        )
    result = search.answer_question(question, state["indexed"], llm.llm_call)
    return JSONResponse(result)


@app.post("/classify")
async def classify(payload: dict):
    new_mail = payload.get("new_mail") or {}
    if not new_mail:
        return JSONResponse({"case_id": "", "error": "new_mail이 필요합니다."})
    case_id = grouping.classify_new_mail(new_mail, state["indexed"], llm.llm_call)
    # 시연용 인메모리 기록 (영속화 없음)
    new_mail = dict(new_mail)
    new_mail["_assigned_case"] = case_id
    state["new_mails"].append(new_mail)
    return JSONResponse({"case_id": case_id, "assigned": new_mail})


@app.get("/versions")
async def versions_route():
    return JSONResponse(versions.version_compare(state["indexed"]))