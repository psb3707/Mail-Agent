# mail-agent — QA/검증자 세션 온보딩

> 이 문서는 `deepwork-mail` 워크스페이스에서 **QA/검증자 역할**을 담당하는
> 세션이 시작할 때 읽는 진입 안내다. 검증 작업을 시작하기 전에 먼저 읽는다.
> 개발자 세션용 상태·작업 계획은 `docs/onboarding.md`를 참조한다.

---

## 1. QA/검증자의 역할

| 책임 | 내용 |
|---|---|
| **커밋 검증** | GitHub 저장소(`psb3707/Mail-Agent`)에 푸시된 커밋을 가져와 검증 |
| **기능 QA** | 같은 워크스페이스의 개발자 세션이 개발·푸시한 기능을 실행 검증 |
| **반복 루프** | 검증 → 피드백 기록 → 재검증의 루프를 반복. 놓치지 말 것 |

**경계**: QA/검증자는 코드를 수정하지 않는다. 발견한 문제는 기록하고
보고·등록하는 것이 역할이다. (수정은 개발자 세션의 몫)

---

## 2. 프로젝트 한 줄

> 메일함을 도착순이 아니라 **건(件) 단위**로 보게 하는 레이어.

가상 메일 400통을 모킹한 해커톤 PoC. "통→건 재조립"을 AI가 판단한다.
시연의 심장은 "왜 이것인가" — 문서 속 실제 값(금액·일자·버전·업체) 인용.

**핵심 제약(검증 시 반드시 확인)**: 원본 `data/mails.json`·`data/attachments/` **무수정**.

---

## 3. 검증 전 알아야 할 현재 상태 (2026-09-10 기준)

| 영역 | 상태 |
|---|---|
| 색인 `scripts/build_index.py` | ✅ (테스트 3/4 — **1건 실패**) |
| 재조립 `app/grouping.py` | ✅ 테스트 3/3 |
| 질의 `app/search.py` | ✅ 테스트 3/3 |
| LLM 게이트웨이 `app/llm.py` | ✅ 테스트 2/2 |
| 버전 `app/versions.py` | ⬜ 미작성 (D1-5) |
| 웹 서빙 `app/main.py`+`templates/` | ⬜ 미작성 (D1-6) |
| 시연 자산(`demo_cache.json`·`slides/`) | ⬜ 미작성 (D1-7) |

**현재 테스트**: `pytest tests -v` → **11 passed, 1 failed**
- 실패: `test_build_index_creates_cases` — 건 A(m0001~m0006) 기대,
  m0005·m0006이 제목 토큰 없어 미편입
- 수리 방향(개발자 문서 §5-1): `_TOKENLESS_KEYWORDS`를 초기 군집 단계에 적용

---

## 4. 검증 워크플로 (반복 루프)

### 4-1. 원격 동기화 + 새 커밋 확인
```cmd
git -C "C:\Users\dksvl\Desktop\coding\deepwork-mail" fetch origin
git -C "C:\Users\dksvl\Desktop\coding\deepwork-mail" log --oneline origin/main -10
```

`docs/monitor/last_seen.txt`(= 마지막으로 검증한 커밋 해시)와 비교해
**새로 도착한 커밋**이 무엇인지 파악한다.

### 4-2. 변경 범위 파악
```cmd
git -C "C:\Users\dksvl\Desktop\coding\deepwork-mail" diff <이전해시>..origin/main --stat
```
- 커밋 단위가 "한 덩어리(D1-n)"인지, 설명이 맞는지 확인
- **원본 데이터(`data/mails.json`·`data/attachments/`)가 변경됐는지 특별히 확인** — 절대 금지 위반

### 4-3. 테스트 실행
```cmd
cd "C:\Users\dksvl\Desktop\coding\deepwork-mail" && .venv\Scripts\python.exe -m pytest tests -v
```
- 새 커밋이 **기존 통과 테스트를 깨지 않았는지** (회귀 확인)
- 실패가 있으면 원인을 분석해 재현 보고에 담는다

### 4-4. 기능 검증 (D1-6 이후)
- 웹 서빙이 생기면 `uvicorn app.main:app` 기동 → `/`에서 카드·토글·질문·버전 표 확인
- 시연 정답 세트(`data/DESIGN.md`) 기준으로 장면 3·4 검증

### 4-5. 결과 기록
- 검증 완료 시 `docs/monitor/last_seen.txt`를 최신 커밋 해시로 갱신
- 발견한 문제는 §5 방식으로 기록·등록

---

## 5. 문제 발견 시 처리

| 심각도 | 처리 |
|---|---|
| **원본 오염** (데이터 수정) | 가장 심각 — 즉시 사용자·PM에게 보고. 코드로 되돌리지 않음(역할 밖) |
| **테스트 실패 / 회귀** | 재현 단계·원인·영향을 보고서로 기록. 칸반 발견 카드로 등록 |
| **제약 위반** (인메모리/캐시 폴백/근거 인용) | 표준 위반 카드로 등록 |
| **문서·코드 불일치** | `doc_mismatch` 카드로 등록 |
| 경미한 개선 제안 | 카드 등록 또는 백로그 기록 (개발자 세션에 전달) |

발견물 등록(Deep Code 칸반):
`kanban_discovery_card` — category: `defect`/`standard_violation`/`doc_mismatch`, 중복은 자동 스킵.

> 원칙: **발견만 하고 수정하지 않는다.** 수정은 개발자 세션의 작업.

---

## 6. QA 체크리스트 (커밋마다)

- [ ] 커밋 단위가 덩어리(D1-n) 하나에 해당하는가
- [ ] 원본 `data/mails.json`·`data/attachments/`가 수정되지 않았는가
- [ ] `pytest tests -v` 전체 통과 (기존 테스트 회귀 없음)
- [ ] 새 기능에 테스트가 있는가 (신규 덩어리인 경우)
- [ ] 도입된 제약 준수: 인메모리(DB 없음), 라이브 기본·캐시 폴백, 근거 인용
- [ ] 파일 구조가 `app/`·`scripts/`·`tests/` 관례를 지키는가
- [ ] `handoff.md` 상태 표(✅/⬜)가 갱신되었는가
- [ ] `docs/monitor/last_seen.txt`가 최신 커밋인가

---

## 7. 참고 문서

| 문서 | 용도 |
|---|---|
| `docs/onboarding.md` | 개발자용 온보딩 — 상태·테스트 현황·남은 작업 순서 |
| `docs/specs/2026-09-09-mail-agent-design.md` | 설계 원본 — 4장면 시나리오·비범위 |
| `handoff.md` | 작업 대장 — 덩어리 7개와 완료 조건 |
| `data/DESIGN.md` | 말투 계승 규칙·시연 정답 세트 (QA 기준) |
| `data/SCHEMA.md` | 데이터 스키마 |
| `docs/BACKLOG.md` | 미해결 판단 |

---

## 8. 워크스페이스 관례

- **위키 정리**: 검증 중 발견한 재사용 가능한 지식(결함 패턴·검증 절차 개선)이 생기면
  `wiki-organize` 스킬에 따라 **deepwork-mail 위키 컬렉션**에 기록한다.
- **한국어**: 출력·보고 기본 언어는 한국어.
- **환경**: Python >=3.11, `.venv` 가상환경, pytest. 실행은 Windows cmd 기준.