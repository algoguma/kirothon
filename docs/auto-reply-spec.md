# 채팅방별 AI 자동 답장 기능 명세

## 1. 개요

여러 사용자가 각자 자기 텔레그램 계정으로 관리자 페이지에 로그인한다. 사용자는 1:1 채팅방 목록에서 원하는 채팅방의 자동 답장을 켜고 끈다. 켜진 채팅방에 상대가 메시지를 보내면 정해진 시간(30초~2분)이 지난 뒤 AI가 대화 내용에 맞춰 만든 답장을 보낸다. 끌 때까지 계속 동작하고, 끄면 켠 시점부터 끈 시점까지의 대화 기록(텍스트)을 내려받을 수 있다.

AI 답장은 개인 클라우드 GPU 서버에서 돌아가는 LLM으로 만든다. 프론트엔드(React)와 백엔드(Python)는 나눠서 구현하며, 둘 다 로컬 PC에서 실행한다.

현재 저장소에는 Telethon 기반 스크립트(`main.py`, `send.py`)만 있다. 백엔드는 이 코드를 바탕으로 만든다.

### 범위

| 포함 | 제외 |
|---|---|
| 1:1 개인 대화 | 그룹, 채널, 봇과의 대화 |
| 여러 사용자, 각자 자기 계정과 자기 LLM API 키 | 한 사용자가 여러 텔레그램 계정을 묶어 관리 |
| AI 생성 답장 | 고정 문구 답장 (AI 실패 시 대체 문구만 사용) |
| 텍스트 기록 추출 | 사진·파일 등 미디어 추출 |
| 로컬 실행 | 클라우드 배포, HTTPS 인증서 설정 |

## 2. 사용자 시나리오

1. 사용자가 관리자 페이지에 접속해 자기 텔레그램 계정으로 로그인한다.
2. 처음 로그인했다면 LLM 연결 정보(API 키 등)를 한 번 입력한다. 서버가 실제로 호출해 보고 저장한다. 다음 로그인부터는 저장된 값이 자동으로 적용된다(3.4).
3. 1:1 채팅방 목록이 보인다.
4. 채팅방마다 있는 on/off 토글로 자동 답장을 켠다. 답장 대기 시간(30~120초)과 AI에게 줄 지침(말투, 상황 등)을 정할 수 있다.
5. 켜진 채팅방에 상대가 메시지를 보내면 대기 시간 뒤 AI가 만든 답장이 나간다. 그 사이 사용자가 직접 답하면 AI 답장은 나가지 않는다. 끌 때까지 계속된다.
6. 토글을 끄면 그 구간(on ~ off)이 하나의 "자동 답장 세션"으로 기록된다.
7. 사용자는 세션 목록에서 원하는 세션을 골라 대화 기록을 보거나 JSON/CSV/TXT로 내려받는다.

## 3. 핵심 기술 결정

### 3.1 봇 계정이 아니라 사용자 계정(userbot)을 쓴다

Bot API 봇은 사용자 본인의 개인 대화를 읽거나 사용자 이름으로 답장할 수 없다. 그래서 지금 코드처럼 Telethon으로 사용자 계정 자체에 로그인하는 방식(MTProto 클라이언트)을 쓴다.

### 3.2 로그인은 "전화번호 + 인증 코드" 방식

텔레그램 로그인 위젯(Login Widget)은 "이 사람이 누구인지"만 확인해 줄 뿐, 메시지를 읽고 보낼 수 있는 세션을 주지 않는다. 따라서 관리자 페이지 로그인은 Telethon의 로그인 절차를 웹으로 옮긴 형태가 된다.

1. 사용자가 전화번호 입력 → 백엔드가 그 사용자용 Telethon 클라이언트를 만들고 `client.send_code_request(phone)` 호출
2. 텔레그램 앱으로 온 코드 입력 → `client.sign_in(phone, code, phone_code_hash=...)`
3. 2단계 인증이 걸려 있으면(`SessionPasswordNeededError`) 비밀번호 입력 → `client.sign_in(password=...)`
4. 성공하면 Telethon 세션(`StringSession`)을 암호화해 DB에 저장하고, 브라우저에는 관리자 페이지용 세션 쿠키를 발급

`API_ID`/`API_HASH`는 이 앱 하나에 대한 값이라 모든 사용자가 같은 값을 쓴다(`.env`). 사용자별로 다른 것은 Telethon 세션과 LLM 설정이다.

### 3.3 사용자별 Telethon 클라이언트

사용자마다 Telethon 클라이언트가 하나씩 필요하다. 백엔드의 `ClientManager`가 `user_id → TelegramClient`를 관리한다.

- 로그인 성공 시 클라이언트를 등록하고 자동 답장 핸들러를 붙인다.
- 백엔드 재시작 시 DB에 저장된 세션으로 모든 사용자의 클라이언트를 다시 연결한다.
- 로그아웃 시 `client.log_out()`으로 텔레그램 쪽 세션도 끊고, DB의 세션을 지운다.
- 기존 `session_name.session` 파일 방식은 사용자 한 명만 지원하므로 `StringSession`으로 바꾼다.

### 3.4 LLM: 개인 클라우드 GPU 서버의 vLLM + 사용자별 API 키

**호출 방식**: GPU 서버에서 vLLM이 모델을 OpenAI 호환 API로 띄운다. 백엔드는 `POST {LLM_BASE_URL}/v1/chat/completions`로 호출하고, 헤더에 `Authorization: Bearer {api_key}`를 넣는다.

```bash
# GPU 서버 쪽 실행 예 (GPU 서버 담당자가 관리)
vllm serve <모델> --served-model-name <모델 이름> --api-key <키> --host 0.0.0.0 --port 8000
```

**서버 주소와 모델은 공통**: 모든 사용자가 같은 GPU 서버를 쓴다. 주소와 모델 이름은 백엔드 `.env`의 `LLM_BASE_URL`, `LLM_MODEL`에 한 번만 적고, 사용자는 입력하지 않는다.

**API 키는 사용자별**: 사용자가 각자 키를 입력하고, 백엔드는 이를 암호화해 사용자 계정에 저장한다(`llm_settings` 테이블, 5장).

- vLLM의 `--api-key`는 서버에 등록된 키와 맞는지만 확인한다. 사용자별 키 발급이나 사용량 집계 기능은 없다. 따라서 지금은 GPU 서버 담당자가 알려 준 키를 사용자가 입력하는 방식이다. 키가 하나뿐이면 모든 사용자가 같은 키를 입력하게 된다.
- 사용자별 키를 따로 발급하거나 사용량을 나눠 보려면 나중에 vLLM 앞에 LiteLLM 같은 프록시를 둔다. 해커톤 범위에서는 하지 않는다.

**"로그인하면 키 등록이 자동으로" 처리 방법**: 처음 로그인할 때 한 번만 키를 입력받는다. 백엔드는 `GET {LLM_BASE_URL}/v1/models`를 그 키로 호출해 키가 맞는지 확인한다. 이 요청은 답장을 생성하지 않아서 GPU를 쓰지 않는다. 확인되면 키를 텔레그램 계정에 묶어 저장한다. 이후에는 텔레그램으로 로그인만 하면 저장된 키가 자동으로 적용되므로 다시 입력할 일이 없다.

**Backend ↔ AI 계약**: AI 담당이 `backend/app/ai/__init__.py`에서 아래 두 함수만 노출하고, 백엔드는 이 함수만 호출한다(AGENTS.md). 내부에서는 `openai` 파이썬 패키지에 `base_url=LLM_BASE_URL + "/v1"`을 지정해 쓴다.

```python
async def generate_reply(api_key: str, history: list[ChatMessage], instructions: str) -> str
    # 실패·시간 초과 시 LLMError를 던진다. 대체 문구 처리는 백엔드가 한다.
async def verify_api_key(api_key: str) -> None
    # GET {LLM_BASE_URL}/v1/models. 실패 시 LLMError.
```

`ChatMessage`는 `sender_name`, `text`, `date`, `is_outgoing`을 가진 dataclass다.

**답장 생성 규칙** (`generate_reply` 내부, AI 담당):

- **시스템 지침**: 기본 지침 + 사용자가 채팅방별로 적은 지침(예: "나는 지금 회의 중이라고 정중하게 안내해 줘")
  - 기본 지침: 사용자 본인처럼 자연스럽게 한국어로 짧게 답할 것, 약속·송금·개인정보 제공 같은 결정은 하지 말 것, 모르는 내용은 지어내지 말 것
- **최근 대화**: 해당 채팅방의 최근 메시지 20개를 `user`(상대) / `assistant`(나) 역할로 넣는다.
- **시간 초과**: 30초. GPU 서버가 꺼져 있거나 첫 요청이 느릴 수 있으므로 다른 API보다 넉넉히 잡는다.
- **실패 처리**: 호출이 실패하거나 시간이 초과되면 `generate_reply`는 `LLMError`를 던진다. 백엔드가 이를 받아 채팅방에 설정된 대체 문구(예: "지금은 답장이 어려워요. 나중에 연락드릴게요.")를 보낸다. 대체 문구가 비어 있으면 답장하지 않는다. 실패 사실은 프론트에서 볼 수 있게 기록한다(`last_error`).

### 3.5 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 프론트엔드 | React + Vite + TypeScript (`strict`) | `localhost:5173` |
| 백엔드 | Python 3.11+, FastAPI, uvicorn | `127.0.0.1:8000`. Telethon과 같은 asyncio 이벤트 루프에서 실행 |
| 텔레그램 | Telethon (기존) + `StringSession` | |
| LLM 호출 | `openai` 파이썬 패키지 (`base_url` 지정) | GPU 서버의 vLLM (OpenAI 호환 API) |
| 저장소 | SQLite (SQLAlchemy 또는 aiosqlite) | 로컬 실행이라 파일 하나로 충분 |
| 암호화 | `cryptography`의 Fernet | Telethon 세션, LLM API 키 |

## 4. 시스템 구성

```
[브라우저]
   │  http://localhost:5173
   ▼
[React (Vite dev server)]
   │  /api/* 요청을 프록시
   ▼
[FastAPI 백엔드 127.0.0.1:8000] ─────────── [SQLite 파일]
   │                                - 사용자, 암호화된 세션·API 키
   ▼                                - 채팅방 설정, 자동 답장 세션, 메시지 로그
[ClientManager]
   ├ 사용자 A의 Telethon 클라이언트 ◀──▶ [Telegram]
   └ 사용자 B의 Telethon 클라이언트 ◀──▶ [Telegram]
   │
   ▼  NewMessage → 대기 → 답장 생성 (사용자별 API 키)
[개인 클라우드 GPU 서버: vLLM (OpenAI 호환 API), 모든 사용자 공통]
```

- **프론트 ↔ 백엔드 연결**: Vite 개발 서버의 `server.proxy`로 `/api`를 `http://127.0.0.1:8000`에 넘긴다. 브라우저 입장에서는 같은 주소라서 CORS 설정과 쿠키 문제가 없다. `localhost`로 적으면 Node 17 이상에서 IPv6(`::1`)로 먼저 연결해, `127.0.0.1`에만 바인딩한 백엔드에 닿지 못할 수 있다.
  ```ts
  // vite.config.ts
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } }
  ```
- FastAPI `lifespan`에서 `ClientManager`를 시작하고, 저장된 세션으로 클라이언트들을 연결한다.
- 켜진 채팅방은 메모리(`dict[user_id, set[chat_id]]`)에 캐시한다. 메시지마다 DB를 조회하지 않기 위해서다. 토글할 때 DB와 캐시를 함께 갱신한다.
- **로컬 실행의 한계**: PC가 꺼지거나 절전 모드에 들어가면 자동 답장도 멈춘다. 시연 중에는 절전 모드를 끈다.

### 저장소 구조

```
kirothon/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            # FastAPI 앱, lifespan에서 ClientManager 시작   (Backend)
│  │  ├─ api/               # auth, me, chats, sessions 라우터              (Backend)
│  │  ├─ telegram/          # ClientManager, 이벤트 핸들러, 디바운스        (Backend)
│  │  ├─ ai/                # generate_reply, verify_api_key, 프롬프트      (AI)
│  │  ├─ models.py, db.py   #                                               (Backend)
│  │  └─ crypto.py          # Fernet 암복호화                               (Backend)
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/                # Vite + React + TypeScript                     (Frontend)
└─ docs/auto-reply-spec.md
```

기존 `main.py`, `send.py`는 참고용으로 두고, 백엔드가 동작하면 정리한다.

## 5. 데이터 모델

모든 테이블에 `user_id`를 두어 사용자 간 데이터를 분리한다. 같은 상대라도 사용자마다 `chat_id`가 같을 수 있으므로 채팅방은 `(user_id, chat_id)`로 식별한다.

### `users`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| telegram_user_id | INTEGER UNIQUE | 텔레그램 계정 ID |
| display_name | TEXT | |
| encrypted_session | BLOB | 암호화된 `StringSession` |
| created_at | DATETIME (UTC) | |

### `llm_settings`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | INTEGER PK | |
| encrypted_api_key | BLOB | 사용자가 입력한 vLLM API 키 (암호화) |
| verified_at | DATETIME NULL | 마지막으로 키 확인(`/v1/models`)에 성공한 시각 |

서버 주소와 모델 이름은 모든 사용자가 같으므로 이 테이블에 두지 않고 `.env`에서 읽는다.

### `chat_settings`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | INTEGER | PK (user_id, chat_id) |
| chat_id | INTEGER | 상대 텔레그램 ID |
| chat_name | TEXT | 표시용 이름 (목록 조회 시 갱신) |
| enabled | BOOLEAN | 자동 답장 on/off |
| reply_delay_sec | INTEGER | 마지막 메시지를 받은 뒤 답장까지 기다리는 시간. 30~120, 기본 30 |
| ai_instructions | TEXT | 이 채팅방에서 AI에게 줄 추가 지침 |
| fallback_text | TEXT NULL | AI 실패 시 보낼 대체 문구 |
| current_session_id | INTEGER NULL | 켜져 있을 때 진행 중인 세션 |
| last_error | TEXT NULL | 마지막 AI 호출 실패 사유 |

### `auto_reply_sessions`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER | |
| chat_id | INTEGER | |
| started_at | DATETIME (UTC) | on 시각 |
| ended_at | DATETIME NULL | off 시각, 진행 중이면 NULL |

### `messages` (텍스트만)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | |
| session_id | INTEGER | |
| user_id | INTEGER | |
| chat_id | INTEGER | |
| message_id | INTEGER | 텔레그램 메시지 ID |
| sender_name | TEXT | |
| text | TEXT | 본문. 미디어만 있는 메시지는 `[사진]`, `[파일]`처럼 종류만 기록 |
| date | DATETIME (UTC) | |
| is_outgoing | BOOLEAN | 내가 보낸 메시지인지 |
| is_auto_reply | BOOLEAN | AI 자동 답장으로 보낸 메시지인지 |

`(user_id, chat_id, message_id)`에 UNIQUE 제약을 걸어 중복 저장을 막는다.

## 6. 동작 상세

### 6.1 켜기 (on)

1. LLM 설정이 없으면 거부한다(`LLM_NOT_CONFIGURED`).
2. `auto_reply_sessions`에 `started_at = now()`로 새 행 생성
3. `chat_settings.enabled = true`, `current_session_id` 설정
4. 메모리 캐시에 `chat_id` 추가

### 6.2 자동 답장 처리 (30~120초 지연)

상대의 **마지막 메시지 뒤로 대기 시간 동안 새 메시지가 없으면** 답장한다(디바운스). 상대가 짧은 메시지를 연달아 보내도 답장은 한 번만 나가고, AI는 연달아 온 메시지를 모두 보고 답한다.

```python
pending: dict[tuple[int, int], asyncio.Task] = {}   # (user_id, chat_id) → 대기 중인 답장

async def on_incoming(user_id, event):
    if not event.is_private or (await event.get_sender()).bot:
        return                                   # 1:1 대화만, 봇 제외
    if event.chat_id not in enabled_chats[user_id]:
        return
    save_message(user_id, event, is_auto_reply=False)

    key = (user_id, event.chat_id)
    if key in pending:
        pending[key].cancel()                    # 대기 타이머 다시 시작
    pending[key] = asyncio.create_task(reply_after_delay(user_id, event.chat_id))

async def on_outgoing(user_id, event):
    # 사용자가 직접 답하면 대기 중인 AI 답장 취소
    if not event.is_private or event.chat_id not in enabled_chats[user_id]:
        return
    if is_sent_by_auto_reply(event):            # AI가 보낸 메시지는 무시
        return
    save_message(user_id, event, is_auto_reply=False)
    task = pending.pop((user_id, event.chat_id), None)
    if task:
        task.cancel()

async def reply_after_delay(user_id, chat_id):
    await asyncio.sleep(settings.reply_delay_sec)
    history = load_recent_messages(user_id, chat_id, limit=20)   # list[ChatMessage]
    try:
        text = await generate_reply(api_key, history, settings.ai_instructions)
    except LLMError as e:
        save_last_error(user_id, chat_id, e)
        if not settings.fallback_text:
            return                               # 대체 문구가 없으면 답장하지 않음
        text = settings.fallback_text
    sent = await client.send_message(chat_id, text)
    save_message(user_id, sent, is_auto_reply=True)
```

주의할 점:

- AI가 보낸 메시지도 `outgoing` 이벤트로 다시 들어온다. `send_message`가 돌려준 메시지 ID를 기억해 두고 `on_outgoing`에서 걸러야 한다(`is_sent_by_auto_reply`).
- 토글을 끄면 그 채팅방의 대기 중인 답장도 취소한다.
- 백엔드를 재시작하면 대기 중이던 답장은 사라진다. 재시작 후에는 다음 메시지부터 다시 동작한다.

### 6.3 끄기 (off)

1. 메모리 캐시에서 `chat_id` 제거, 대기 중인 답장 취소
2. 진행 중인 세션의 `ended_at = now()` 기록
3. `chat_settings.enabled = false`, `current_session_id = NULL`

### 6.4 기록 추출

- **DB 로그 (기본)**: 세션 ID로 `messages`를 조회한다. 어떤 메시지가 AI 답장이었는지 구분된다.
- **텔레그램에서 다시 조회 (보완)**: 백엔드가 꺼져 있던 동안의 메시지는 DB에 없다. 이 경우 `client.iter_messages(chat_id, offset_date=started_at, reverse=True)`로 `ended_at`까지 다시 가져와 빈 구간을 채운다.

텍스트만 추출한다. 미디어 메시지는 `[사진]`, `[파일]`처럼 종류만 표시하고, 캡션이 있으면 캡션을 함께 넣는다.

출력 형식:

- **JSON**: 전체 필드
- **CSV**: `date, sender_name, text, is_auto_reply` (UTF-8 BOM 포함, 엑셀에서 한글 깨짐 방지)
- **TXT**: `[2026-11-14 10:23] 홍길동: 안녕하세요`, AI 답장은 `[2026-11-14 10:24] 나 (AI): ...`

## 7. API 명세 (프론트 ↔ 백엔드 계약)

프론트와 백엔드가 동시에 작업할 수 있도록 요청·응답 형식을 여기서 고정한다. 바꿀 때는 이 문서를 먼저 고친다. 백엔드가 준비되기 전에는 프론트가 이 형식으로 목(mock) 데이터를 만들어 개발한다. FastAPI가 자동 생성하는 `http://127.0.0.1:8000/docs`(OpenAPI)에서 실제 형식을 확인할 수 있다.

### 공통 규칙

- 모든 경로는 `/api`로 시작한다.
- 인증은 HttpOnly 쿠키(`session`)로 한다. 프론트는 토큰을 따로 다루지 않는다. 같은 주소(Vite 프록시)라서 `fetch`에 별도 옵션이 필요 없다.
- 시각은 ISO 8601 UTC 문자열(`2026-11-14T01:23:45Z`)로 주고받고, 화면에서 KST로 바꿔 보여준다.
- 로그인한 사용자 본인의 데이터만 다룬다. 남의 `chat_id`나 `session_id`를 넣으면 404를 반환한다.
- 오류 응답 형식:
  ```json
  { "error": { "code": "LLM_NOT_CONFIGURED", "message": "LLM 설정이 필요합니다." } }
  ```

| 오류 코드 | HTTP | 의미 |
|---|---|---|
| `UNAUTHORIZED` | 401 | 로그인 필요 |
| `INVALID_CODE` | 400 | 인증 코드가 틀림 |
| `PASSWORD_REQUIRED` | 401 | 2단계 인증 비밀번호 필요 |
| `INVALID_PASSWORD` | 400 | 2단계 인증 비밀번호가 틀림 |
| `FLOOD_WAIT` | 429 | 텔레그램 요청 제한. `retry_after_sec` 포함 |
| `LLM_NOT_CONFIGURED` | 400 | LLM 설정 없음 |
| `LLM_TEST_FAILED` | 400 | LLM 테스트 호출 실패 |
| `VALIDATION_ERROR` | 422 | 입력값 오류 (예: 대기 시간 범위 밖) |
| `NOT_FOUND` | 404 | 없거나 남의 데이터 |

### 7.1 인증

**`POST /api/auth/send-code`**
```json
// 요청
{ "phone": "+821012345678" }
// 응답 200
{ "login_id": "b3f1c2..." }
```
`login_id`는 진행 중인 로그인을 가리키는 임시 ID다. 백엔드는 여기에 Telethon 클라이언트와 `phone_code_hash`를 묶어 메모리에 10분간 보관한다.

**`POST /api/auth/sign-in`**
```json
// 요청
{ "login_id": "b3f1c2...", "code": "12345" }
// 응답 200 (쿠키 발급)
{ "user": { "id": 1, "display_name": "홍길동" }, "llm_configured": false }
// 2단계 인증이 걸려 있으면 401 PASSWORD_REQUIRED
```

**`POST /api/auth/password`**
```json
// 요청
{ "login_id": "b3f1c2...", "password": "..." }
// 응답 200: sign-in 성공 응답과 같음
```

**`POST /api/auth/logout`** → 204. 텔레그램 세션을 끊고 DB에서 지운다.

### 7.2 내 정보와 LLM 설정

**`GET /api/me`** → 페이지를 새로 열 때 로그인 상태 확인용
```json
{ "user": { "id": 1, "display_name": "홍길동" }, "llm_configured": true }
```

**`GET /api/me/llm`**
```json
{ "model": "qwen2.5-7b-instruct", "api_key_set": true, "api_key_hint": "...a1b2",
  "verified_at": "2026-11-14T01:00:00Z" }
```
`model`은 `.env`의 `LLM_MODEL`을 보여주기만 한다(읽기 전용). API 키 원문은 절대 내려주지 않고 끝 4자리만 보여준다.

**`PUT /api/me/llm`**
```json
// 요청
{ "api_key": "..." }
// 응답 200: GET /api/me/llm 과 같음
// 저장 전에 GET {LLM_BASE_URL}/v1/models 로 키를 확인하고, 실패하면 400 LLM_TEST_FAILED (저장하지 않음)
```

### 7.3 채팅방

**`GET /api/chats?q=검색어`** → 1:1 채팅방 목록, 최근 대화 순
```json
[
  { "chat_id": 123456789, "name": "김철수", "last_message_at": "2026-11-14T01:20:00Z",
    "enabled": true, "reply_delay_sec": 30, "ai_instructions": "회의 중이라고 안내",
    "fallback_text": "나중에 연락드릴게요.", "current_session_id": 7, "last_error": null }
]
```

**`PUT /api/chats/{chat_id}/auto-reply`**
```json
// 요청 (바꿀 필드만 보내도 됨)
{ "enabled": true, "reply_delay_sec": 60, "ai_instructions": "...", "fallback_text": "..." }
// 응답 200: 위 목록의 항목 하나와 같은 형식
```
`reply_delay_sec`이 30~120 밖이면 422. LLM 설정이 없는데 켜려고 하면 400 `LLM_NOT_CONFIGURED`.

### 7.4 자동 답장 세션과 기록

**`GET /api/chats/{chat_id}/sessions`** → 최신순
```json
[
  { "id": 7, "started_at": "2026-11-14T01:00:00Z", "ended_at": null,
    "message_count": 12, "auto_reply_count": 4 }
]
```

**`GET /api/sessions/{session_id}/messages`** → 화면에서 미리 보기
```json
[
  { "message_id": 555, "sender_name": "김철수", "text": "안녕", "date": "2026-11-14T01:01:00Z",
    "is_outgoing": false, "is_auto_reply": false }
]
```

**`GET /api/sessions/{session_id}/export?format=json|csv|txt`** → 파일 다운로드
`Content-Disposition: attachment; filename="김철수_2026-11-14_1000-1130.csv"`. 진행 중인 세션은 현재 시각까지 추출한다.

## 8. 화면 (프론트엔드)

| 경로 | 화면 | 사용하는 API |
|---|---|---|
| `/login` | 전화번호 → 인증 코드 → (필요 시) 2FA 비밀번호, 한 페이지에서 단계 전환 | `/auth/*` |
| `/setup` | API 키 입력란 하나 + "저장" 버튼(저장 시 연결 확인). `llm_configured: false`면 로그인 직후 여기로 이동 | `/me/llm` |
| `/chats` | 1:1 채팅방 목록: 이름, 마지막 대화 시각, on/off 토글, 설정 버튼(대기 시간 슬라이더 30~120초, AI 지침, 대체 문구), 오류 표시(`last_error`), 검색창 | `/chats` |
| `/chats/:chatId/sessions` | 세션 목록(시작·종료 시각, 메시지 수, AI 답장 수), 대화 미리 보기, 형식별 다운로드 버튼 | `/chats/{id}/sessions`, `/sessions/*` |
| `/settings` | LLM 설정 변경, 로그아웃 | `/me/llm`, `/auth/logout` |

- 앱 시작 시 `GET /api/me`로 로그인 상태를 확인하고, 401이면 `/login`으로 보낸다.
- 켜져 있는 채팅방의 답장 상태는 `/chats`를 10초마다 다시 불러와 갱신한다. 실시간 알림(WebSocket)은 해커톤 범위에서 제외한다.

## 9. 보안과 운영 주의사항

- **Telethon 세션은 계정 전체 권한과 같다.** 유출되면 누구나 그 계정으로 메시지를 읽고 보낼 수 있다. 세션과 LLM API 키는 Fernet으로 암호화해 저장하고, 암호화 키(`ENCRYPTION_KEY`)는 `.env`에 DB와 분리해 둔다. `.gitignore`에는 이미 `.env`, `*.session`, `*.db`가 들어 있다.
- **로컬에서만 연다.** 백엔드는 `127.0.0.1:8000`에만 바인딩한다(`uvicorn --host 127.0.0.1`). 같은 네트워크의 다른 기기에서 접속해야 하면 그때 HTTPS를 적용한다.
- **GPU 서버 연결**: 로컬 백엔드에서 클라우드 GPU 서버로 가는 요청은 인터넷을 지나간다. vLLM은 반드시 `--api-key`를 켜고 실행해야 한다. 키 없이 띄우면 주소를 아는 누구나 GPU를 쓸 수 있다. vLLM 자체는 HTTPS를 제공하지 않으므로, 가능하면 앞에 nginx나 Caddy를 두어 HTTPS로 연결한다. 해커톤 중 HTTP로 쓴다면 키가 평문으로 오간다는 점을 알고 쓴다.
- **사용자 간 데이터 분리**: 모든 조회에 `user_id` 조건을 건다. 남의 ID로 요청하면 404가 나오는지 확인한다.
- **AI 답장의 위험**: AI가 사용자 대신 약속을 하거나 사실과 다른 말을 할 수 있다. 3.4의 기본 지침으로 줄이고, 기록에 AI 답장을 구분해 표시한다.
- **로그인 시도 제한**: 같은 전화번호로 인증 코드를 짧은 간격으로 반복 요청하면 텔레그램이 계정을 일시 제한한다. 백엔드에서 1분에 1회로 막는다.
- **FloodWait 처리**: 텔레그램이 `FloodWaitError`를 주면 지정된 시간만큼 기다린 뒤 재시도하고, 프론트에는 `FLOOD_WAIT`로 알린다.
- **텔레그램 이용약관**: 사용자 계정 자동화는 스팸으로 판단되면 계정이 정지될 수 있다. 자동 답장은 본인이 켠 1:1 채팅방에만, 상대 메시지에 대한 응답으로만 보낸다. 시연은 팀원끼리의 대화로 한다.
- **시간대**: DB와 API는 UTC, 화면과 추출 파일만 KST.

### 백엔드 `.env` 항목

```
API_ID=...
API_HASH=...
ENCRYPTION_KEY=...          # Fernet.generate_key()로 생성
LLM_BASE_URL=https://...    # GPU 서버의 vLLM 주소 (/v1 앞까지)
LLM_MODEL=...               # vLLM의 --served-model-name 값
LLM_TIMEOUT_SEC=30
```

API 키는 `.env`에 넣지 않는다. 사용자가 화면에서 입력한다.

## 10. 구현 순서 (프론트·백엔드 병렬)

| 단계 | 백엔드 | 프론트엔드 |
|---|---|---|
| 0 | 이 문서의 7장 API 형식 확정 (함께) | |
| 1 | FastAPI 뼈대, DB 모델, Fernet 암호화 | Vite + React 프로젝트, 라우팅, 7장 형식의 목 데이터 |
| 2 | 웹 로그인 (send-code / sign-in / password), `ClientManager` | 로그인 화면 3단계 |
| 3 | `/me/llm` 저장 (`verify_api_key` 호출) | `/setup` 화면 |
| 4 | 채팅방 목록 (`send.py`의 `iter_dialogs` 재사용, `dialog.is_user`로 필터), on/off와 세션 생성·종료 | 채팅방 목록, 토글, 설정 모달 |
| 5 | 지연 답장과 메시지 로그 (처음엔 고정 문구로 확인) → `generate_reply`에 GPU 서버 연결 | 오류 표시, 10초 주기 갱신 |
| 6 | 세션 목록, 미리 보기, 추출 (JSON → CSV → TXT) | 세션 화면, 다운로드 |
| 7 | 목 데이터를 실제 API로 교체하고 통합 테스트, 시연 시나리오 점검 (함께) | |

## 11. 결정 사항

| 항목 | 결정 |
|---|---|
| 대기 시간 | 사용자가 채팅방마다 30~120초 중에서 고름. 기본 30초 |
| 사용자가 직접 답하면 | 대기 중인 AI 답장 취소 |
| LLM | 개인 클라우드 GPU 서버의 vLLM, OpenAI 호환 API로 호출 |
| GPU 서버 주소·모델 | 모든 사용자 공통, 백엔드 `.env`에 설정 |
| API 키 | 사용자가 첫 로그인 때 한 번 입력, 이후 자동 적용 |
| 실행 환경 | 로컬 PC (프론트 `:5173`, 백엔드 `:8000`) |
| 구현 분담 | 프론트 React, 백엔드 Python(FastAPI) |

## 12. GPU 서버 담당자에게 받아야 할 것

- `LLM_BASE_URL`: vLLM 서버 주소 (예: `https://gpu.example.com`)
- `LLM_MODEL`: `--served-model-name` 값
- 사용자가 입력할 API 키
- 동시에 몇 개의 요청까지 처리할 수 있는지 (여러 사용자의 답장이 겹칠 때 확인용)
