# mail-agent — Render Free 배포용 Dockerfile (지시-019)
# 베이스: Python 3.13 slim (종속성·pyproject 기반)
FROM python:3.13-slim

# 작업 디렉토리
WORKDIR /app

# 의존성 먼저 복사 (레이어 캐시 활용)
COPY pyproject.toml README.md ./
COPY app ./app
COPY agent ./agent

# 의존성 설치 (PoC — DB·빌드 도구 불필요, 순수 런타임 의존성)
RUN pip install --no-cache-dir -e .

# 데이터·정적 파일 복사 (원본 무수정, 읽기 전용)
COPY data ./data
COPY scripts ./scripts

# uvicorn 시작 — Render의 $PORT 환경변수 사용 (지시-019 완료 조건 2)
# Render는 무료 티어에서 $PORT를 자동 주입한다 (기본 10000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]