# mail-agent

> 메일함을 도착순이 아니라 **건(件) 단위**로 보게 하는 레이어

사내 해커톤 출품작. 설계 문서는 `docs/specs/2026-09-09-mail-agent-design.md`.

## 현재 상태 — PoC 구현 완료, 시연 리허설 진행 중

| 산출물 | 상태 |
|---|---|
| `data/mails.json` | ✅ 가상 메일 400통 / 9개 건 / 첨부 16개 |
| `data/attachments/` | ✅ 진짜 PDF·XLSX 16개 (한글 텍스트 추출 검증 완료) |
| `data/DESIGN.md` | ✅ 말투 계승 규칙, 건 구성, 시연 정답 세트 |
| `scripts/generate_data.py` | ✅ 재현 가능 (seed 고정) |
| `scripts/generate_attachments.py` | ✅ |
| `scripts/build_index.py` | ✅ 9건/43통 재조립 · 비건 357통 · `indexed.json` 생성 |
| `tests/test_build_index.py` | ✅ 정합성 · 라벨 비의존 · 순서 무관 · 멱등 · 최신본 검증 |
| `app/` (FastAPI 단일 페이지) | ✅ 재조립·질의·버전·신메일 분류 라우트 구현 |

## 실행 방법 (로컬 시연, Windows)

```powershell
pip install -e .                        # 1. 설치
copy .env.example .env                  # 2. .env 열어 OPENROUTER_API_KEY 입력 (키가 없어도 폴백으로 시연 가능)
.\run.ps1                               # 3. 실행 → http://localhost:8765
```

- `.env`에 키를 넣으면 라이브 LLM 호출, 비워 두면 캐시 폴백으로 동작합니다.

## Render 배포 (GitHub 자동 배포, 무료 티어)

> 발표는 다른 PC에서 진행되므로 로컬 실행 대신 Render에 올려 브라우저로 접속한다.

```bash
# 1. 이 레포를 GitHub에 올린 뒤, Render 대시보드에서 New → Blueprint로 render.yaml 선택 (또는 Blueprint sync)
# 2. Render 대시보드 → Environment에서 OPENROUTER_API_KEY 설정 (레포에는 키를 절대 커밋하지 않음)
# 3. 배포 완료 후 발표 PC에서 https://<service-name>.onrender.com/ 접속
```

- 키를 설정하면 라이브 LLM 호출, 미설정이면 캐시 폴백으로 동작합니다 (동일 URL, 동작만 다름).
- 상세 절차·환경변수·콜드 스타트(keep-alive) 대응은 `docs/RENDER_DEPLOY.md` 참조.

## 데이터 재생성

```bash
python3 -m venv .venv && ./.venv/bin/pip install -e .
./.venv/bin/python scripts/generate_data.py
./.venv/bin/python scripts/generate_attachments.py
./.venv/bin/python scripts/build_index.py
```

## 기술 스택 — 단계별 역할

> 핵심 원칙: 메일의 "도착 → 재조립 → 질의 → 답변" 각 단계에서
> *규칙으로 되는 판단은 규칙으로, 규칙으로 안 되는 판단(같은 건 · 같은 문서의
> 어느 버전인가)에만 AI를 쓴다.*
>
> 가벼운 단계(도착·색인·화면)는 검증된 도구가 맡고, 무거운 단계(재조립·정답·버전)는
> 항상 LLM 호출이 기본이며 캐시는 네트워크 장애 시 자동 폴백으로만 동작한다.

### 0. 데이터 생성 계층 (사전 준비)

| 도구 | 역할 | 비유 |
|---|---|---|
| `generate_data.py` | 말투 계승 400통 · 9건 · 첨부 16개 메타데이터 생성 | 가상 메일함 준비 |
| `generate_attachments.py` | 실제 PDF/엑셀 첨부 파일 생성 (금액·일자·버전을 문자열로 심음) | 근거 인용 재료 만들기 |
| `reportlab` | PDF 첨부 렌더링 | 문서 서식 출력 |
| `openpyxl` | XLSX 첨부 생성 | 스프레드시트 출력 |
| `pypdf` | (색인 계층에서) PDF 텍스트 추출 | 서류 복사 |

> 구분: `openpyxl`은 **생성**(첨부 모킹)과 **추출**(색인) 양쪽에서 쓰인다.

### 1. 도착·색인 계층 (`scripts/build_index.py`)

| 도구 | 역할 | 비유 |
|---|---|---|
| Python `re` 정규화 | 말머리·`RE:`·`_`·공백 정규화 + 프로젝트 토큰 추출 | 이름표의 표기 흔들림 평준화 |
| `pypdf` | PDF 본문 텍스트 추출 | 서류를 복사기로 복사 |
| `openpyxl` (`read_only` 모드) | 엑셀 셀 텍스트 추출 | 표를 횡성한 카드로 정리 |
| 안정 키(대표 메일 id) | 건 ID를 콘텐츠 기반으로 고정 → 재실행해도 흔들림 없음 (멱등) | 폴더 이름을 내용으로 고정 |
| `tests/test_build_index.py` | index 무결성·순서 무관(재현) 검증 | 품질 보험 |

**결과물** `data/indexed.json`: `cases[]` (건 그룹) · `attachment_texts` (첨부 전문) ·
`version_groups[]` (버전 계열) · `non_cases` (비건 처리).

### 2. 재조립 판단 계층 `app/grouping.py` (장면 2)

| 도구 | 역할 | 비유 |
|---|---|---|
| LLM (Claude) | "이 통들이 같은 건인가" 내용 기반 판단 | 같은 일을 함께 본 사람의 알아차림 |
| 캐시(cache) | 네트워크 장애 시 사전 계산 답으로 자동 전환 | 폴백, 기본 경로 아님 |

> 이 계층은 항상 `indexed.json`을 **읽기만** 한다. 원본 메일함은 절대 수정하지 않는다.

### 3. 자연어 질의 계층 `app/search.py` (장면 3)

| 단계 | 도구 | 비유 |
|---|---|---|
| ① 질문에서 단서 추출 | LLM 1회 | "어느 서류인지 대충 짐작" |
| ② 후보 축소 (5~10개) | `indexed.json` 필터 · 키워드 | 몇 장만 꺼내기 |
| ③ 정답 선정 + 근거 인용 | LLM 1회 → 문서 속 실제 값을 인용 | "이 금액이 그 파일에 적혀 있습니다" |
| 폴백 | `llm.py` 캐시 | 네트워크 끊겨도 데모 유지 |

### 4. 버전 판별 계층 `app/versions.py` (장면 4)

| 도구 | 역할 | 비유 |
|---|---|---|
| LLM | 파일명 · 내용 비교로 버전 계열 판별 | 같은 문서의 몇 번째 저장본인지 가림 |
| 캐시 | 장애 시 사전 계산 · 폴백 | 폴백 전용 |

### 5. 서빙 계층 `app/main.py` + `templates/index.html`

| 도구 | 역할 | 비유 |
|---|---|---|
| FastAPI + uvicorn | 웹 서버, 라우트 4개 (`/`, `/ask`, `/classify`, `/versions`) | 접수 창구 |
| Jinja2 | 단일 페이지 템플릿에 데이터 끼워 넣기 | 화면 골격 + 실데이터 |
| 인메모리 저장 | 동적 구조는 세션 전용 (영속화 비범위) | 데모용 휘발 기록 |

### 계층 의존성 흐름

```
[도착·색인] build_index.py (정규화 + pypdf + openpyxl)
      ↓  indexed.json (읽기 전용 · 원본 무수정)
[재조립]    grouping.py ──→ LLM(Claude) ──→ 캐시 폴백
[질의]      search.py   ──→ LLM 1회(단서) + LLM 1회(근거) ──→ 캐시 폴백
[버전]      versions.py ──→ LLM ──→ 캐시 폴백
      ↓
[서빙]      main.py (FastAPI) + templates/index.html (Jinja2)
             토글: 도착순 ↔ 건 단위 · 질문창 · 근거 표시
```

### 선택 이유 (규칙 vs AI 경계)

- **규칙으로 되는 것**: 말머리·접두사 정규화, 프로젝트 토큰 추출, 건 ID 안정 키, 첨부 텍스트 추출, 파일명 버전 패턴 — 모두 검증된 도구(Python 표준 · pypdf · openpyxl)로 충분.
- **AI로 맡기는 것**: "같은 건인가"(내용 기반 재조립), "정답 문서 선택 + 근거 인용", "같은 문서의 어느 버전인가" — 규칙으로는 불가능한 판단만.
- **캐시의 지위**: 기본 경로가 아니라 장애 시 자동 폴백. 라이브 호출이 기본이므로 데모가 "짜고 치는" 것으로 보이지 않는다.

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

## AI 답변 UI 및 관리 Agent

웹 질문은 `ManagerAgent`와 실제 메일 도구를 통해 처리합니다. `agent/prompts.py`의 공통 말투 지침으로 핵심부터 자연스럽게 답하고, 문서 근거를 함께 제공합니다. 최근 메일 요약은 최신 12통의 수신일·본문을 사용하며 조회 기간을 표시합니다.

답변은 Markdown 제목·목록·표를 렌더링하고, 출처 접기 및 크게 보기를 제공합니다. HTML과 원격 이미지는 렌더링하지 않습니다. 컨텍스트는 요청 단위이며 후속 질문에 이전 답변이 자동 전달되는 다중 턴 채팅은 아직 지원하지 않습니다.
