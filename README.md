# mail-agent

> 메일함을 도착순이 아니라 **건(件) 단위**로 보게 하는 레이어

사내 해커톤 출품작. 설계 문서는 `docs/specs/2026-09-09-mail-agent-design.md`.

## 현재 상태 — 사전 준비(데이터) 완료, 애플리케이션 미착수

해커톤 규정상 사전 코딩 허용 범위가 확인되지 않아 **데이터까지만** 만들어 둔 상태다.

| 산출물 | 상태 |
|---|---|
| `data/mails.json` | ✅ 가상 메일 400통 / 9개 건 / 첨부 16개 |
| `data/attachments/` | ✅ 진짜 PDF·XLSX 16개 (한글 텍스트 추출 검증 완료) |
| `data/DESIGN.md` | ✅ 말투 계승 규칙, 건 구성, 시연 정답 세트 |
| `scripts/generate_data.py` | ✅ 재현 가능 (seed 고정) |
| `scripts/generate_attachments.py` | ✅ |
| `scripts/build_index.py` | ⬜ 당일 |
| `app/` (FastAPI 단일 페이지) | ⬜ 당일 |

## 데이터 재생성

```bash
python3 -m venv .venv && ./.venv/bin/pip install openpyxl reportlab pypdf
./.venv/bin/python scripts/generate_data.py
./.venv/bin/python scripts/generate_attachments.py
```

## 데이터가 시연을 성립시키는 방식

**장면 1 — 무엇을 검색해도 막힌다** (조작이 아니라 표기 관행 때문)

| 검색어 | 결과 | 문제 |
|---|---|---|
| `N_CX` | 4건 | 정답 첨부가 붙은 메일이 **누락** (`〔Project N CX〕` 언더바 없음) |
| `견적` | 4건 | 1·3차 취합본 + **다른 프로젝트 견적서**가 섞여 최종본 판별 불가 |

**장면 2 — 하나의 건이 6통에 흩어져 있다** (`_case: "A"`)
제목이 서로 다르고, 말머리 표기가 흔들리고, 스레드가 끊긴 메일이 섞여 있다.

**장면 3 — 세 문서 중에서 골라야 한다**
`견적취합_v3`(정답) / `견적취합_v1`(산정기준 미통일) / `D-MIG_이관비용_견적서`(다른 건).
정답 문서에는 인용할 실제 값이 있다 — **(주)디자인랩스 48,500,000원(VAT 별도), 2026-05-12 3차 취합본**.

## 남은 판단

`docs/BACKLOG.md` 참조. 특히 **사전 코딩 규정 확인**과 **동료 미니 설문**.
