---
inclusion: always
---

# 기술 스택과 구조

| 영역 | 선택 |
|---|---|
| Frontend | React + Vite + TypeScript, `localhost:5173`, `/api`는 Vite proxy로 `127.0.0.1:8080`에 전달 |
| Backend | Python 3.11+, FastAPI, uvicorn (`--host 127.0.0.1 --port 8080`) |
| Telegram | Telethon + `StringSession` (사용자 계정, Bot API 아님) |
| AI | `openai` 패키지, `base_url = LLM_BASE_URL + "/v1"`, GPU 서버의 vLLM. SSH 터널(`127.0.0.1:8000`)로 접속, API 키 없음 |
| DB | SQLite (SQLAlchemy async 또는 aiosqlite) |
| 암호화 | `cryptography` Fernet (Telethon 세션, 텔레그램 `api_hash`) |

```
backend/
  app/
    main.py          # FastAPI 앱, lifespan에서 ClientManager 시작
    api/             # auth, me, chats, sessions 라우터        (Backend)
    telegram/        # ClientManager, 이벤트 핸들러, 디바운스  (Backend)
    ai/              # generate_reply, 프롬프트                 (AI)
    models.py, db.py, crypto.py                               (Backend)
  requirements.txt
  .env.example
frontend/            # Vite + React                           (Frontend)
docs/auto-reply-spec.md
```

- Telethon과 FastAPI는 같은 asyncio 이벤트 루프에서 돈다. 블로킹 호출(동기 HTTP, `time.sleep`)을 쓰지 않는다.
- 패키지 추가는 `backend/requirements.txt`(버전 고정) 또는 `frontend/package.json`에만 한다. Frontend 패키지 매니저는 npm으로 통일한다.
