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

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Literal
from uuid import UUID
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app import grouping, llm, versions
from app.answer_format import format_answer
from agent.manager import ManagerAgent
from app.inbox import MailboxStore

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data"
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="mail-agent PoC")

# 서버 시작 시 사전 계산 결과를 인메모리로 로드 (읽기 전용)
_indexed = json.loads((DATA / "indexed.json").read_text(encoding="utf-8"))

_raw = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
mailbox = MailboxStore(_indexed, _raw["mails"])


class ReceiveRequest(BaseModel):
    event_id: UUID
    scenario: Literal["existing", "new_case", "alert"] = "existing"


@app.post("/inbox/receive", status_code=202)
def receive(payload: ReceiveRequest, background_tasks: BackgroundTasks):
    event_id = str(payload.event_id)
    try:
        event = mailbox.begin(event_id, payload.scenario)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if event["status"] == "received":
        background_tasks.add_task(mailbox.process, event_id, llm.llm_call)
    return event


@app.get("/inbox/events/{event_id}")
def receive_status(event_id: UUID):
    event = mailbox.event(str(event_id))
    if event is None:
        raise HTTPException(404, "수신 이벤트를 찾을 수 없어요.")
    return event


@app.post("/inbox/mails/{mail_id}/read")
def read_mail(mail_id: str):
    if not mailbox.mark_read(mail_id):
        raise HTTPException(404, "메일을 찾을 수 없어요.")
    return {"id": mail_id, "is_new": False}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    indexed = mailbox.snapshot()
    cards = grouping.reassemble(indexed)
    for card in cards:
        card["new_count"] = sum(bool(m.get("_is_new")) for m in card["mails"])
    version_rows = versions.version_compare(indexed)
    non_cases = indexed.get("non_cases", [])
    alerts = [n for n in non_cases if n.get("type") == "alert"]
    misc = [n for n in non_cases if n.get("type") != "alert"]
    raw = json.loads((DATA / "mails.json").read_text(encoding="utf-8"))
    mails = sorted(indexed["mails"], key=lambda m: m.get("sent_at", ""), reverse=True)
    filenames = {a["id"]: a["filename"] for a in raw["attachments"]}
    # starlette 1.6.0 신형 시그니처: TemplateResponse(request, name, context)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "cards": cards,
            "mails": mails,
            "filenames": filenames,
            "attachment_count": len(raw["attachments"]),
            "grouped_count": sum(len(c["mails"]) for c in cards),
            "version_rows": version_rows,
            "alerts": alerts,
            "misc": misc,
            "new_mails": [m for m in mails if m.get("_is_new")],
            "recent_received": [m for m in mails if m["id"].startswith("m-inbound-")][:5],
            "latest_event": mailbox.latest_event(),
        },
    )


@app.post("/ask")
def ask(payload: dict):
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(
            {"answer": "질문을 입력해 주세요.", "attachment": None,
             "evidence": [], "mail_ids": [], "cached": False}
        )
    indexed = mailbox.snapshot()
    result = ManagerAgent(indexed=indexed, llm_call=llm.llm_call).run_result(question)
    # Source links always resolve against the actual read-only mailbox.
    mails = grouping._mails_from(indexed)
    if result.get("attachment") and not result.get("mail_ids"):
        attachments = indexed.get("attachments", [])
        aids = {a["id"] for a in attachments if a.get("filename") == result["attachment"] or a["id"] == result["attachment"]}
        result["mail_ids"] = [mid for mid, m in mails.items() if aids.intersection(m.get("attachments", []))]
    return JSONResponse(format_answer(result, mails))


@app.post("/classify")
def classify(payload: dict):
    # Backward-compatible preview; receiving and saving uses /inbox/receive.
    new_mail = payload.get("new_mail") or {}
    if not new_mail:
        return JSONResponse({"case_id": "", "error": "new_mail이 필요합니다."})
    result = grouping.classify_new_mail(new_mail, mailbox.snapshot(), llm.llm_call)
    assigned = {**new_mail, "_assigned_case": result.get("case_id", ""), "_decision": result.get("decision", "")}
    return {**result, "assigned": assigned}


@app.get("/versions")
async def versions_route():
    return JSONResponse(versions.version_compare(mailbox.snapshot()))