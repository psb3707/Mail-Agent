# mail-agent — Render Free 배포 실행·검증 문서 (지시-019)

> 목표: 해커톤 발표 PC가 다른 PC이므로, 이 워크스페이스를 **Render 무료 티어 서버**에
> 배포해 발표 PC가 브라우저로 접속만 하면 되게 한다. GitHub push → 자동 배포.
>
> 배경 (사용자 확정 2026-09-10): 발표는 다른 PC에서 진행 → 로컬 uvicorn만으로 불가.
> 서버리스(Vercel·Cloudflare·Supabase)는 파일기반+인메모리+라이브 LLM 특성상 부적합 →
> **Render Free** (Dockerfile 기반) 선택.

---

## 1. 구성 파일

| 파일 | 역할 |
|---|---|
| `Dockerfile` | `python:3.13-slim` + 의존성 설치 + `uvicorn --port $PORT`, 데이터 포함 |
| `render.yaml` | Render Blueprint — web service + `$PORT` + env vars + 시작 명령 |
| `.dockerignore` | `.venv/`·`__pycache__/`·`.env`·`PM/`·`.git` 등 제외 (이미지 경량화·보안) |
| `README.md` | 배포 절차 3줄 + 접속 URL + 폴백 안내 |
| 본 문서 | 배포 단계·환경변수·콜드 스타트 대응 절차 |

---

## 2. 배포 단계 (최초 1회)

1. **GitHub 준비**: 이 레포(`psb3707/Mail-Agent`)가 GitHub에 push되어 있어야 한다
   (커밋·push는 PM 담당 — 본 문서의 파일이 커밋된 뒤에 진행).
2. **Render 가입·연동**: https://render.com → GitHub 계정 연동 (레포 읽기 권한).
3. **Blueprint 연결** (자동 배포 + 인프라 선언):
   - Render 대시보드 → **New** → **Blueprint** → `psb3707/Mail-Agent` 선택.
   - `render.yaml`이 감지되면 미리보기가 뜬다 → **Apply**.
   - 서비스명은 `mail-agent` → 접속 URL `https://mail-agent.onrender.com/` (지정 가능).
4. **API 키 설정** (대시보드 env var — 레포 커밋 금지):
   - 서비스 → **Environment** → `OPENROUTER_API_KEY` 추가 (OpenRouter 키).
   - 선택: `OPENROUTER_MODEL` (기본 `anthropic/claude-sonnet-4-5`).
   - **주의**: `.env`·키는 절대 커밋하지 않는다. `render.yaml`의
     `sync: false` env var는 대시보드에서만 값을 넣는 필드다.
5. **수동 Deploy** → 빌드·시작 로그 확인 → **Live** 상태 확인.

## 3. 이후 자동 배포

- GitHub `main`(기본 브랜치)에 push되면 `autoDeployTrigger: commit`에 따라 자동 배포.
- Dockerfile·render.yaml 변경도 push로 반영된다.

---

## 4. 환경변수

| 변수 | 용도 | 설정 위치 | 미설정 시 동작 |
|---|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter 라이브 LLM 호출용 키 | Render 대시보드 **only** (레포 금지) | 캐시/기본 메시지 폴백 (지시-017) |
| `OPENROUTER_MODEL` | 모델 ID (기본 `anthropic/claude-sonnet-4-5`) | Render enviroment / `.env.example` | 기본 모델 사용 |
| `PORT` | Render가 주입하는 포트 (기본 10000) | Render가 자동 주입 — 별도 설정 불필요 | `Dockerfile`·`render.yaml`이 `$PORT`를 uvicorn에 전달 |

**폴백 동작 확인 방법**: 키를 빈 값으로 두고 배포 → `/ask` 질의 시
`cached: true` + 사전 계산 답변(`data/demo_cache.json`)이 돌아온다.
키를 넣으면 `cached: false` + 라이브 OpenRouter 호출.

---

## 5. 로컬 사전 검증 (Docker)

지시-019 완료 조건 4 — 커밋 전에 로컬에서 이미지 빌드·스모크한다.

```powershell
# 1. 이미지 빌드 (문법·복사 검증)
docker build -t mail-agent:local .

# 2. 컨테이너 실행 (Render와 동일 조건: PORT 주입 + 키 없음 → 폴백)
docker run --rm -d -p 10000:10000 -e PORT=10000 --name mail-agent-test mail-agent:local

# 3. 스모크
curl -s -o /dev/null -w "%{http_code}" http://localhost:10000/          # 200
curl -s -X POST http://localhost:10000/ask -H "Content-Type: application/json" -d "{\"question\":\"N_CX 외주 견적 최종 얼마\"}"

# 4. 정리
docker stop mail-agent-test
```

- `/ask`는 키 미설정 상태에서는 `cached: true` + demo_cache 정답이어야 한다.
- Windows 콘솔 인코딩(cp949) 때문에 한글이 깨져 보이면 응답을 파일로 저장해
  `read_file`(UTF-8)로 확인한다. (서버 동작 자체와는 무관)

---

## 6. 콜드 스타트 대응 (keep-alive)

Render Free 웹 서비스는 **15분간 요청이 없으면 인스턴스가 잠들고(sleep)**,
다음 요청 때 다시 뜬다(콜드 스타트 30초~1분). 발표 당일 문제를 막으려면:

1. **발표 직전**: 발표 PC(또는 폰)에서 URL을 열어 **미리 웨이크업** → 이후 15분은 즉시 응답.
2. **아이스브레이커**: 발표 시작 전 인사·소개 시간(1~2분)에 자연스럽게 첫 접속.
3. **장기 유지(선택)**: 무료 티어에서 항상 깨어 있게 하려면 외부 모니터링(예: Kuma, cron-job.org,
   UptimeRobot 무료 5분 간격)으로 `GET /`을 주기 호출. 잠들지 않음(무료 한도 내).
4. **폴백 안전망**: 잠들었다 깨어난 직후 `/ask` 첫 호출이 느릴 수 있음 → 발표에서
   "질문 후 2~3초" 흐름이면 문제없지만, 대비해 **정답 2건을 캐시에 보유**(이미 `demo_cache.json`).
5. Render Free는 1개월 무휴 사용 시 인스턴스를 중지할 수 있음(정책) → 해커톤 발표일
   전날·당일 아침에 URL로 재확인한다.

---

## 7. 트러블슈팅

| 증상 | 원인 | 대처 |
|---|---|---|
| 배포가 `Build` 단계에서 실패 | Dockerfile 문법·의존성 설치 오류 | 로컬 `docker build`로 재현 → 로그 확인 |
| 시작 직후 `Crash` | `$PORT` 미전달·모듈 import 오류 | Render 로그에서 uvicorn 라인 확인, 로컬 `docker run -e PORT=10000` 재현 |
| `/`는 뜨데 `/ask`가 5xx | OpenRouter 키 형식·네트워크 | 키 재설정, 폴백 동작 확인(키 없이도 200) |
| 첫 접속이 30초+ 걸림 | 무료 티어 콜드 스타트 | 위 §6 keep-alive 적용 |
| 한글이 깨져 보임 | Windows 콘솔 cp949 | 서버는 UTF-8 정상 — 브라우저/`read_file`로 확인 |

---

## 8. 완료 조건 대조

| # | 완료 조건 | 상태 |
|---|---|---|
| 1 | Dockerfile·render.yaml·.dockerignore 존재 + 문법 검증 | ✅ (로컬 docker build로 검증) |
| 2 | `$PORT` → uvicorn 전달 | ✅ `CMD uvicorn ... --port ${PORT:-10000}` |
| 3 | 키 미설정 → 폴백 / 설정 → 라이브 (문서화) | ✅ §4 참조 |
| 4 | 로컬 docker build → run → `GET /` 200 + `/ask` 폴백 | ✅ (본 문서 §5) |
| 5 | README·본 문서에 절차 기록 | ✅ |