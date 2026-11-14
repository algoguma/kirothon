# kirothon

텔레그램 1:1 채팅방별 AI 자동 답장 서비스 (Kirothon 해커톤).

- 명세: [docs/auto-reply-spec.md](docs/auto-reply-spec.md)
- 팀 역할과 작업 규칙: [AGENTS.md](AGENTS.md)

## 구성

| 경로 | 내용 | 실행 |
|---|---|---|
| `frontend/` | React + Vite + TypeScript | `http://localhost:5173` |
| `backend/` | Python FastAPI + Telethon | `http://127.0.0.1:8080` |

## 실행 (Windows PowerShell)

필요: Python 3.11+, Node.js LTS. PowerShell에서 `npm`이 실행 정책 오류를 내면 `npm.cmd`로 실행한다.

**백엔드**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env        # 값 채우기. LLM_USE_STUB=true면 GPU 서버 없이 동작
# ENCRYPTION_KEY는 필수. 아래 출력값을 .env의 ENCRYPTION_KEY=에 붙여 넣는다 (없으면 서버가 시작되지 않음)
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```
- 실제 GPU 서버를 쓰려면(`LLM_USE_STUB=false`) 별도 터미널에서 SSH 터널을 먼저 연다: `ssh -N -L 8000:localhost:8000 <user>@<GPU 서버>` (비밀번호는 GPU 서버 담당자에게 받는다). `.env`는 `LLM_BASE_URL=http://127.0.0.1:8000`. 그래서 백엔드는 `8080`을 쓴다.
- 반드시 `backend` 폴더 안에서 실행한다. `.env`와 `kirothon.db`를 현재 폴더 기준으로 찾는다.
- 텔레그램 `api_id`/`api_hash`는 `.env`에 넣지 않는다. 로그인 화면에서 각자 자기 값을 입력한다 (https://my.telegram.org 에서 발급).
- 구현된 API: `POST /api/auth/send-code`, `/api/auth/sign-in`, `/api/auth/password`, `/api/auth/logout`, `GET /api/me`. 나머지는 아직 없으니 프론트는 해당 화면을 mock으로 개발한다.
확인: http://127.0.0.1:8080/api/health, API 문서: http://127.0.0.1:8080/docs
린트: `.venv\Scripts\ruff format .; .venv\Scripts\ruff check .`

**프론트엔드**
```powershell
cd frontend
npm.cmd install
Copy-Item .env.example .env.local  # VITE_USE_MOCK=true면 mock 데이터, false면 백엔드 호출
npm.cmd run dev
```
실제 백엔드로 로그인해 보려면 `.env.local`을 `VITE_USE_MOCK=false`로 바꾸고, 백엔드를 먼저 띄운 뒤 `npm.cmd run dev`를 다시 실행한다.
http://localhost:5173 , 린트와 빌드: `npm.cmd run lint`, `npm.cmd run build`

## 역할별 시작 지점

| 역할 | 시작 파일 |
|---|---|
| Frontend | `frontend/src/App.tsx`(라우트), `frontend/src/api/`(타입, mock) |
| Backend | `backend/app/main.py`, `models.py`, `api/`, `telegram/` |
| AI | `backend/app/ai/__init__.py`(계약 + stub). 구현은 `ai/` 아래 모듈로 나눠도 된다 |

## Kiro 사용

이 저장소는 Kiro 설정(`.kiro/`)을 공유한다. clone 후 저장소 루트에서 `kiro-cli`를 실행하면 `team` 에이전트와 `claude-opus-5.5` 모델이 자동으로 적용된다. 모델을 바꾸지 않는다.

- PR 만들기: 세션에서 `/pr`
- 머지 전 셀프 리뷰: `kiro-cli --agent reviewer`
