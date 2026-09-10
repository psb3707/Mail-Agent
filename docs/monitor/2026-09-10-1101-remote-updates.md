# 원격 저장소 업데이트 감시 보고

감시 시각: 2026-09-10 11:01 (KST)
기준 커밋(직전): `cdb2bda9f40a7fa902a74b30aed700b25e148247`

## 새 커밋 요약 (3건)

### 1. `ada555f4b27a608c032a6c58e7a787fe47854c3e` — docs: add QA reviewer onboarding guide
- 작성자: KEEKE132 (2026-09-10 01:57 UTC)
- 변경 파일:
  - `docs/onboarding-qa.md` (신규, +135)
- 요약: QA/검증자 세션용 온보딩 문서 추가. 커밋 검증·기능 QA·반복 검증 루프 정의와 발견물 칸반 등록 절차 명시. 개발자 온보딩(`docs/onboarding.md`)과 상호 연결.

### 2. `be439d4e9e0b18d6171bd1a6ee4fa0efbd349675` — Merge remote-tracking branch 'origin/main'
- 작성자: seoungbeom (2026-09-10 01:56 UTC)
- 변경 파일:
  - `AGENTS.md` (수정, +1)
  - `docs/onboarding.md` (신규, +127)
- 요약: 개발자 세션 온보딩 문서 추가 및 AGENTS.md에 "새 세션은 온보딩을 읽는다" 자동 주입 라인 추가. 현재 상태(11 passed/1 failed), 다음 할 일(D1-5~D1-7), 전역 제약 기록.

### 3. `25ca00a2732d46fea07a7392a39cf1b293b75a47` — Merge remote-tracking branch 'origin/main'
- 작성자: seoungbeom (2026-09-10 01:55 UTC)
- 변경 파일:
  - `docs/specs/2026-09-10-mail-agent-storage-layers.md` (신규, +78)
- 요약: 저장소 3계층 구조 설계 문서 추가(원본 불변 / 분류 트리 파생물 / 에이전트 매니페스트 indexed.json). PoC/데모에서는 실제 심볼릭 링크 대신 가상 트리(indexed.json) 주력 권고.

## 참고
- 기준 커밋(`cdb2bda`)부터 최신(`ada555f`)까지 총 3건의 커밋이 원격에 새로 도착.
- 원본 데이터(`data/mails.json`·`data/attachments/`) 변경 없음 (문서/온보딩 추가 전부).
- 변경 핵심: **QA/개발자 온보딩 문서 신설 + AGENTS.md 자동 주입 + 저장소 3계층 설계 명문화** → 워크스페이스 진입점·협업 기준이 확립됨.
