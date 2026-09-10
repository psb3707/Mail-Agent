# main 자동 PM 리뷰 운영 가이드

## 목적

`main` 브랜치에 push가 발생할 때마다 변경 사항을 **mail-agent 총괄 PM 관점**에서 검토한다.
리뷰는 해당 커밋의 GitHub 댓글로 즉시 전달되고 동일한 Markdown 문서는 GitHub Actions
artifact로 30일 동안 보관된다.

단순 코드 스타일보다 다음을 우선한다.

- "메일 통 → 업무 건"이라는 문제 정의와의 정합성
- 4개 시연 장면의 완성도와 회귀 위험
- 원본 메일 무수정, DB 없음, 라이브 LLM 기본·캐시 폴백 제약
- 건 분류의 순서 무관·멱등·증분 편입
- 첨부 근거 인용과 버전 판별 정확성
- 비건 메일 과잉 편입 위험
- 테스트 증거, 개인정보 반출 경계, 해커톤 범위

## 구성

| 파일 | 역할 |
|---|---|
| `.github/workflows/pm-review.yml` | `main` push 감지, 테스트, 리뷰 생성, 댓글·artifact 게시 |
| `scripts/pm_review.py` | 안전한 리뷰 입력 수집, Claude 호출, Markdown 생성, GitHub 댓글 게시 |
| `tests/test_pm_review.py` | 민감 경로 제외와 리뷰 문서 생성 규칙 검증 |

## 최초 설정

GitHub 저장소에서 다음 값을 설정한다.

1. **Settings → Secrets and variables → Actions → Secrets**
2. Repository secret `ANTHROPIC_API_KEY` 추가
3. 선택 사항으로 **Variables**에 `ANTHROPIC_MODEL` 추가
   - 미설정 기본값: `claude-sonnet-5`

API 키는 코드나 `.env` 파일에 커밋하지 않는다. Secret이 없으면 workflow는 설정 방법을
담은 실패 문서를 커밋 댓글과 artifact로 남긴 후 실패 처리된다. Secret 추가 후 Actions의
**PM Review** 화면에서 `Run workflow`로 다시 실행할 수 있다.

## 실행 흐름

```text
main push
   ↓
전체 Git history checkout
   ↓
pytest 실행
   ↓
프로젝트 기준 문서 + 안전한 diff + 테스트 결과 수집
   ↓
Claude PM 리뷰 생성
   ├─ 해당 commit에 Markdown 댓글
   └─ GitHub Actions artifact 30일 보관
```

`workflow_dispatch`도 지원하므로 GitHub Actions 화면에서 수동 리뷰를 다시 실행할 수 있다.

## 외부 전송 경계

자동 리뷰는 소스코드 전체나 실제 메일함을 무제한으로 외부에 보내지 않는다. 다음 경로는
모델 입력에서 강제로 제외한다.

- `.env` 및 변형 파일
- `data/mails.json`
- `data/indexed.json`
- `data/attachments/`
- `data/samples/`
- 인증서·개인키·secret/credential 이름을 가진 파일

모델에는 민감 경로를 제외한 변경 diff, 테스트 결과, 파일 목록과 다음 프로젝트 기준 문서만
전달한다.

- `README.md`
- `AGENTS.md`
- `handoff.md`
- 핵심 설계 문서
- 데이터 설계·스키마 문서
- 백로그

메일 본문이나 첨부 내용을 리뷰에 포함해야 하는 예외가 생기면 코드에서 제외 규칙을 완화하지
말고, 먼저 사내 반출 정책과 익명화 기준을 확정한다.

## 결과 해석

리뷰 판정은 세 단계다.

| 판정 | 의미 |
|---|---|
| `GO` | 현재 범위에서 진행 가능 |
| `GO WITH FIXES` | 진행 가능하지만 명시된 보완이 필요 |
| `NO-GO` | 핵심 가치·정확성·보안·시연을 위협하는 차단 문제 존재 |

발견 사항의 우선순위는 `[P0]`에서 `[P3]` 순이다. 자동 리뷰는 PM 의사결정을 돕는 보조
수단이며, 코드 작성자와 총괄 PM의 최종 판단을 대체하지 않는다.

## 운영상 주의사항

- push마다 API 호출 비용이 발생한다.
- 대용량 diff는 입력 상한을 넘는 부분이 생략되므로 큰 변경은 여러 커밋으로 나눈다.
- 테스트 실패가 있어도 리뷰 생성과 댓글 게시를 먼저 시도한 뒤 workflow를 실패 처리한다.
- 생성 실패 시 오류 문서가 남으므로 Actions 로그와 커밋 댓글에서 원인을 확인한다.
- 저장소 텍스트와 diff는 프롬프트 명령이 아니라 검토 자료로만 취급하도록 시스템 지시를 둔다.
