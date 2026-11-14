# 채팅방별 AI 자동 답장 기능 명세

## 1. 개요

여러 사용자가 각자 자기 텔레그램 계정으로 관리자 페이지에 로그인한다. 사용자는 1:1 채팅방 목록에서 원하는 채팅방의 자동 답장을 켜고 끈다. 켜진 채팅방에 상대가 메시지를 보내면 정해진 시간(5초~2분)이 지난 뒤 AI가 대화 내용에 맞춰 만든 답장을 보낸다. 끌 때까지 계속 동작하고, 끄면 켠 시점부터 끈 시점까지의 대화 기록(텍스트)을 내려받을 수 있다.

AI 답장은 개인 클라우드 GPU 서버에서 돌아가는 LLM으로 만든다. 프론트엔드(React)와 백엔드(Python)는 나눠서 구현하며, 둘 다 로컬 PC에서 실행한다.

현재 저장소에는 Telethon 기반 스크립트(`main.py`, `send.py`)만 있다. 백엔드는 이 코드를 바탕으로 만든다.

### 범위

| 포함 | 제외 |
|---|---|
| 1:1 개인 대화 | 그룹, 채널, 봇과의 대화 |
| 여러 사용자, 각자 자기 계정·자기 텔레그램 `api_id`/`api_hash` | 한 사용자가 여러 텔레그램 계정을 묶어 관리 |
| AI 생성 답장 | 고정 문구 답장 (AI 실패 시 대체 문구만 사용) |
| 텍스트 기록 추출 | 사진·파일 등 미디어 추출 |
| 로컬 실행 | 클라우드 배포, HTTPS 인증서 설정 |

## 2. 사용자 시나리오

1. 사용자가 관리자 페이지에 접속해 자기 `api_id`/`api_hash`(https://my.telegram.org 에서 미리 발급)와 전화번호를 입력하고, 자기 텔레그램 계정으로 로그인한다.
2. 1:1 채팅방 목록이 보인다. LLM 연결은 백엔드가 공통으로 설정하므로 사용자가 입력할 것은 없다(3.4).
3. 채팅방마다 있는 on/off 토글로 자동 답장을 켠다. 답장 대기 시간(5~120초)과 AI에게 줄 지침(말투, 상황 등)을 정할 수 있다.
4. 켜진 채팅방에 상대가 메시지를 보내면 대기 시간 뒤 AI가 만든 답장이 나간다. 그 사이 사용자가 직접 답하면 AI 답장은 나가지 않는다. 끌 때까지 계속된다.
5. 토글을 끄면 그 구간(on ~ off)이 하나의 "자동 답장 세션"으로 기록된다.
6. 사용자는 세션 목록에서 원하는 세션을 골라 대화 기록을 보거나 JSON/CSV/TXT로 내려받는다.

## 3. 핵심 기술 결정

### 3.1 봇 계정이 아니라 사용자 계정(userbot)을 쓴다

Bot API 봇은 사용자 본인의 개인 대화를 읽거나 사용자 이름으로 답장할 수 없다. 그래서 지금 코드처럼 Telethon으로 사용자 계정 자체에 로그인하는 방식(MTProto 클라이언트)을 쓴다.

### 3.2 로그인은 "전화번호 + 인증 코드" 방식

텔레그램 로그인 위젯(Login Widget)은 "이 사람이 누구인지"만 확인해 줄 뿐, 메시지를 읽고 보낼 수 있는 세션을 주지 않는다. 따라서 관리자 페이지 로그인은 Telethon의 로그인 절차를 웹으로 옮긴 형태가 된다.

1. 사용자가 자기 `api_id`, `api_hash`, 전화번호 입력 → 백엔드가 그 값으로 Telethon 클라이언트(`TelegramClient(StringSession(), api_id, api_hash)`)를 만들고 `client.send_code_request(phone)` 호출. `api_id`/`api_hash`가 틀리면 Telethon이 `ApiIdInvalidError`를 던진다.
2. 텔레그램 앱으로 온 코드 입력 → `client.sign_in(phone, code, phone_code_hash=...)`
3. 2단계 인증이 걸려 있으면(`SessionPasswordNeededError`) 비밀번호 입력 → `client.sign_in(password=...)`
4. 성공하면 Telethon 세션(`StringSession`)을 암호화해 DB에 저장하고, 브라우저에는 관리자 페이지용 세션 쿠키를 발급

**`api_id`/`api_hash`는 사용자별로 입력받는다.** 강민석이 로그인하면 강민석의 값으로, 김기철이 로그인하면 김기철의 값으로 클라이언트를 만든다. 백엔드 `.env`에는 이 값을 두지 않는다.

- 이 두 값은 "어떤 앱이 접속하는지"를 나타낼 뿐 계정 접근 권한을 주지 않는다. 그래서 값을 입력해도 전화번호 + 인증 코드 로그인은 여전히 필요하다.
- 사용자는 https://my.telegram.org → "API development tools"에서 앱을 만들어 두 값을 미리 받아 둔다. 자동으로 가져오는 공식 방법은 없다.
- 로그인에 성공하면 `api_id`와 암호화한 `api_hash`를 Telethon 세션과 함께 `users`에 저장한다. 세션은 그 세션을 만든 `api_id`/`api_hash`로만 다시 연결할 수 있기 때문이다.
- 로그아웃하면 세션과 함께 지운다. 다시 로그인할 때 다시 입력한다.

### 3.3 사용자별 Telethon 클라이언트

사용자마다 Telethon 클라이언트가 하나씩 필요하다. 백엔드의 `ClientManager`가 `user_id → TelegramClient`를 관리한다.

- 로그인 성공 시 클라이언트를 등록하고 자동 답장 핸들러를 붙인다.
- 백엔드 재시작 시 DB에 저장된 사용자별 `api_id`/`api_hash`와 세션으로 모든 사용자의 클라이언트를 다시 연결한다.
- 로그아웃 시 `client.log_out()`으로 텔레그램 쪽 세션도 끊고, DB의 세션을 지운다.
- 기존 `session_name.session` 파일 방식은 사용자 한 명만 지원하므로 `StringSession`으로 바꾼다.

### 3.4 LLM: 개인 클라우드 GPU 서버의 vLLM (SSH 터널, API 키 없음)

**호출 방식**: GPU 서버에서 vLLM이 모델을 OpenAI 호환 API로 띄운다. 백엔드는 `POST {LLM_BASE_URL}/v1/chat/completions`로 호출한다.

**접속 방식**: vLLM은 GPU 서버의 `127.0.0.1:8000`에만 열고 `--api-key` 없이 실행한다. 백엔드를 실행하는 PC에서 SSH(비밀번호 로그인)로 터널을 열어 접속한다. GPU 서버에 SSH로 로그인할 수 있는 사람만 쓸 수 있으므로 별도 API 키를 두지 않는다.

```bash
# GPU 서버 (GPU 서버 담당자가 관리, prototype/server/serve.sh)
vllm serve <모델> --served-model-name <모델 이름> --host 127.0.0.1 --port 8000

# 백엔드를 실행하는 PC (별도 터미널에서 켜 둔다)
ssh -N -L 8000:localhost:8000 <user>@<GPU 서버>
# → LLM_BASE_URL=http://127.0.0.1:8000
```

**서버 주소와 모델은 공통**: 모든 사용자가 같은 GPU 서버를 쓴다. 주소와 모델 이름은 백엔드 `.env`의 `LLM_BASE_URL`, `LLM_MODEL`에 한 번만 적고, 사용자는 화면에서 아무것도 입력하지 않는다.

**Backend ↔ AI 계약**: AI 담당이 `backend/app/ai/__init__.py`에서 아래 함수만 노출하고, 백엔드는 이 함수만 호출한다(AGENTS.md). 내부에서는 `openai` 파이썬 패키지에 `base_url=LLM_BASE_URL + "/v1"`을 지정해 쓴다.

```python
async def generate_reply(history: list[ChatMessage], instructions: str) -> str
    # 기본 답장. 분석이 없거나 실패한 채팅방에서 쓴다. 실패·시간 초과 시 LLMError.
async def analyze_chat(work_dir: str, history: list[ChatMessage], me: str, partner: str) -> None
    # history를 work_dir/history.json으로 저장하고 말투(style.md)·기억(memory.md)을 뽑는다. 실패 시 LLMError.
def persona_ready(work_dir: str) -> bool
    # style.md와 memory.md가 모두 있으면 True.
async def generate_persona_reply(work_dir: str, history: list[ChatMessage], me: str, partner: str,
                                 instructions: str) -> PersonaReply
    # 분석 결과로 답장. 실패 시 LLMError.
    # PersonaReply(text, input, emergency: Emergency(severity, reason) | None, confirmation_question: str | None)
    # prototype/run.py JSON의 reply / input / emergency / needs_confirmation과 같은 정보. note는 목록 표시용 한 줄 요약.
```

`ChatMessage`는 `sender_name`, `text`, `date`, `is_outgoing`을 가진 dataclass다.

**말투·기억 분석 답장** (`prototype/`의 분석 로직을 `backend/app/ai/persona/`로 옮긴 것, AI 담당):

1. **켤 때**: 백엔드가 텔레그램에서 그 채팅방의 최근 메시지 최대 1000개를 가져와 `analyze_chat`을 백그라운드로 호출한다. `history.json`은 텔레그램 내보내기 형식(`{"messages": [{"type", "date", "from", "text"}]}`, 시각은 KST)이다. 분석은 최근 500개로 말투를, 1000개 전체로 약속·사건·상대 정보를 뽑으며 30초~2분 걸린다.
2. **답장할 때**: 분석이 끝난 채팅방은 `generate_persona_reply`로, 분석이 실패한 채팅방은 `generate_reply`로 답한다. 분석 중이면 답장을 미뤘다가 분석이 끝난 뒤 답한다(6.2). 백엔드는 최근 메시지 160개를 넘기고, 상대가 마지막으로 보낸 메시지들을 새 메시지로, 그 앞의 최근 150개를 원문으로 프롬프트에 넣는다.
3. **판단**: 답장 전에 한 번 더 호출해 비상상황과 "주인 확인 필요"를 판단한다.
   - 주인 확인 필요(기억에 없는 약속·결정)면 "확인해보고 알려줄게" 같은 보류 답장만 보내고, 주인에게 물을 질문을 `confirmation_question`으로 돌려준다.
   - 비상상황이면 진지한 톤으로 답하고 심각도·사유를 `emergency`로 돌려준다.
   - 백엔드는 요약(`note`)을 `last_error`에 기록해 채팅방 목록에 보여 준다.
   - **주인 알림**: 둘 중 하나라도 해당하면 답장을 보낸 뒤, 사용자 본인의 "저장된 메시지"에 알림을 한 번 보낸다. 자기에게 보낸 메시지는 푸시 알림이 오지 않으므로 5초 뒤 예약 메시지(`schedule`)로 보내 리마인더 알림이 뜨게 한다. 형식:
     ```
     🚨 비상 알림 [낮음]            ❓ 확인이 필요해요
     기철 · 16:44                   기철: "오빠 고향 어디야?"
     "오빠 나 배아파."              기철 님 고향이 어디인지 알려 주세요.
     (사유)
     ```
     비상이면 비상 알림만 보낸다. 알림에 답해 상대에게 전달하는 기능은 범위 밖이다.
4. **페르소나**: 사용자 본인으로 답한다. 기본 지침(약속·송금·개인정보 결정 금지, 지어내지 말 것)과 채팅방 지침을 함께 넣는다.
5. **끌 때**: `work_dir`(`backend/data/<user_id>/<chat_id>/`)를 지운다. 다시 켜면 다시 분석한다. 로그아웃하면 그 사용자의 폴더 전체를 지운다.

**기본 답장 규칙** (`generate_reply` 내부, AI 담당):

- **시스템 지침**: 기본 지침 + 사용자가 채팅방별로 적은 지침(예: "나는 지금 회의 중이라고 정중하게 안내해 줘")
  - 기본 지침: 사용자 본인처럼 자연스럽게 한국어로 짧게 답할 것, 약속·송금·개인정보 제공 같은 결정은 하지 말 것, 모르는 내용은 지어내지 말 것
- **최근 대화**: 해당 채팅방의 최근 메시지 20개를 `user`(상대) / `assistant`(나) 역할로 넣는다.
- **시간 초과**: 30초. GPU 서버가 꺼져 있거나 첫 요청이 느릴 수 있으므로 다른 API보다 넉넉히 잡는다.
- **실패 처리**: 호출이 실패하거나 시간이 초과되면 `generate_reply`는 `LLMError`를 던진다. 백엔드가 이를 받아 채팅방에 설정된 대체 문구(예: "지금은 답장이 어려워요. 나중에 연락드릴게요.")를 보낸다. 대체 문구가 비어 있으면 답장하지 않는다. 실패 사실은 프론트에서 볼 수 있게 기록한다(`last_error`).

### 3.5 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 프론트엔드 | React + Vite + TypeScript (`strict`) | `localhost:5173` |
| 백엔드 | Python 3.11+, FastAPI, uvicorn | `127.0.0.1:8080`. Telethon과 같은 asyncio 이벤트 루프에서 실행. `8000`은 vLLM SSH 터널이 쓴다 |
| 텔레그램 | Telethon (기존) + `StringSession` | |
| LLM 호출 | `openai` 파이썬 패키지 (`base_url` 지정) | GPU 서버의 vLLM (OpenAI 호환 API) |
| 저장소 | SQLite (SQLAlchemy 또는 aiosqlite) | 로컬 실행이라 파일 하나로 충분 |
| 암호화 | `cryptography`의 Fernet | Telethon 세션, 텔레그램 `api_hash` |

## 4. 시스템 구성

```
[브라우저]
   │  http://localhost:5173
   ▼
[React (Vite dev server)]
   │  /api/* 요청을 프록시
   ▼
[FastAPI 백엔드 127.0.0.1:8080] ─────────── [SQLite 파일]
   │                                - 사용자, 암호화된 세션·api_hash
   ▼                                - 채팅방 설정, 자동 답장 세션, 메시지 로그
[ClientManager]
   ├ 사용자 A의 Telethon 클라이언트 ◀──▶ [Telegram]
   └ 사용자 B의 Telethon 클라이언트 ◀──▶ [Telegram]
   │
   ▼  NewMessage → 대기 → 답장 생성
[SSH 터널 127.0.0.1:8000] ══ SSH ══▶ [GPU 서버: vLLM 127.0.0.1:8000, 모든 사용자 공통]
```

- **프론트 ↔ 백엔드 연결**: Vite 개발 서버의 `server.proxy`로 `/api`를 `http://127.0.0.1:8080`에 넘긴다. 브라우저 입장에서는 같은 주소라서 CORS 설정과 쿠키 문제가 없다. `localhost`로 적으면 Node 17 이상에서 IPv6(`::1`)로 먼저 연결해, `127.0.0.1`에만 바인딩한 백엔드에 닿지 못할 수 있다.
  ```ts
  // vite.config.ts
  server: { proxy: { '/api': 'http://127.0.0.1:8080' } }
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
│  │  ├─ ai/                # generate_reply, 프롬프트                      (AI)
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
| api_id | INTEGER | 사용자가 입력한 텔레그램 `api_id` |
| encrypted_api_hash | BLOB | 암호화된 `api_hash` |
| encrypted_session | BLOB | 암호화된 `StringSession` |
| created_at | DATETIME (UTC) | |

### `chat_settings`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| user_id | INTEGER | PK (user_id, chat_id) |
| chat_id | INTEGER | 상대 텔레그램 ID |
| chat_name | TEXT | 표시용 이름 (목록 조회 시 갱신) |
| enabled | BOOLEAN | 자동 답장 on/off |
| reply_delay_sec | INTEGER | 마지막 메시지를 받은 뒤 답장까지 기다리는 시간. 5~120, 기본 30 |
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

1. `auto_reply_sessions`에 `started_at = now()`로 새 행 생성
2. `chat_settings.enabled = true`, `current_session_id` 설정
3. 메모리 캐시에 `chat_id` 추가
4. 말투·기억 분석을 백그라운드로 시작(3.4). 분석 상태는 `analysis_status`(`running` → `ready` 또는 `failed`)로 채팅방 목록에 내려 준다. 백엔드를 다시 시작했을 때 분석이 없으면 다시 분석한다.

### 6.2 자동 답장 처리 (5~120초 지연)

상대의 **마지막 메시지 뒤로 대기 시간 동안 새 메시지가 없으면** 답장한다(디바운스). 상대가 짧은 메시지를 연달아 보내도 답장은 한 번만 나가고, AI는 연달아 온 메시지를 모두 보고 답한다.

**분석 중에는 기다린다**: 대기 시간이 지났는데 말투·기억 분석(6.1의 4)이 아직 끝나지 않았으면, 분석이 끝날 때까지 기다린 뒤 분석 결과로 답한다. 분석 없이 엉뚱한 답장이 나가지 않게 하기 위해서다. 기다리는 동안에도 사용자가 직접 답하거나 상대가 새 메시지를 보내면 지금처럼 취소되거나 다시 시작한다. 분석이 실패하면 기본 답장(`generate_reply`)으로 답한다.

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
        text = await generate_reply(history, settings.ai_instructions)
    except LLMError as e:
        save_last_error(user_id, chat_id, e)
        if not settings.fallback_text:
            return                               # 대체 문구가 없으면 답장하지 않음
        text = settings.fallback_text
    sent = await client.send_message(chat_id, text)
    save_message(user_id, sent, is_auto_reply=True)
```

주의할 점:

- AI 답장은 줄마다 텔레그램 메시지 하나로 나눠 보낸다(말풍선, 최대 5개, 사이 1.2초). 보내는 도중 사용자가 직접 메시지를 보내거나 자동 답장을 끄면 남은 줄은 보내지 않는다. 각 메시지는 `is_auto_reply=true`로 기록한다.
- AI가 보낸 메시지도 `outgoing` 이벤트로 다시 들어온다. `send_message`가 돌려준 메시지 ID를 기억해 두고 `on_outgoing`에서 걸러야 한다(`is_sent_by_auto_reply`).
- 토글을 끄면 그 채팅방의 대기 중인 답장도 취소한다.
- 백엔드를 재시작하면 대기 중이던 답장은 사라진다. 재시작 후에는 다음 메시지부터 다시 동작한다.

### 6.3 끄기 (off)

1. 메모리 캐시에서 `chat_id` 제거, 대기 중인 답장과 분석 취소, 분석 폴더(`history.json`, `style.md`, `memory.md`) 삭제
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

프론트와 백엔드가 동시에 작업할 수 있도록 요청·응답 형식을 여기서 고정한다. 바꿀 때는 이 문서를 먼저 고친다. 백엔드가 준비되기 전에는 프론트가 이 형식으로 목(mock) 데이터를 만들어 개발한다. FastAPI가 자동 생성하는 `http://127.0.0.1:8080/docs`(OpenAPI)에서 실제 형식을 확인할 수 있다.

### 공통 규칙

- 모든 경로는 `/api`로 시작한다.
- 인증은 HttpOnly 쿠키(`session`)로 한다. 프론트는 토큰을 따로 다루지 않는다. 같은 주소(Vite 프록시)라서 `fetch`에 별도 옵션이 필요 없다.
- 시각은 ISO 8601 UTC 문자열(`2026-11-14T01:23:45Z`)로 주고받고, 화면에서 KST로 바꿔 보여준다.
- 로그인한 사용자 본인의 데이터만 다룬다. 남의 `chat_id`나 `session_id`를 넣으면 404를 반환한다.
- 오류 응답 형식:
  ```json
  { "error": { "code": "NOT_FOUND", "message": "채팅방을 찾을 수 없습니다." } }
  ```

| 오류 코드 | HTTP | 의미 |
|---|---|---|
| `UNAUTHORIZED` | 401 | 로그인 필요 |
| `INVALID_API_CREDENTIALS` | 400 | `api_id`/`api_hash`가 틀림 (`ApiIdInvalidError`) |
| `INVALID_CODE` | 400 | 인증 코드가 틀림 |
| `PASSWORD_REQUIRED` | 401 | 2단계 인증 비밀번호 필요 |
| `INVALID_PASSWORD` | 400 | 2단계 인증 비밀번호가 틀림 |
| `FLOOD_WAIT` | 429 | 텔레그램 요청 제한. `retry_after_sec` 포함 |
| `VALIDATION_ERROR` | 422 | 입력값 오류 (예: 대기 시간 범위 밖) |
| `NOT_FOUND` | 404 | 없거나 남의 데이터 |

### 7.1 인증

**`POST /api/auth/send-code`**
```json
// 요청
{ "api_id": 1234567, "api_hash": "0123456789abcdef0123456789abcdef", "phone": "+821012345678" }
// 응답 200
{ "login_id": "b3f1c2..." }
// api_id/api_hash가 틀리면 400 INVALID_API_CREDENTIALS
```
`login_id`는 진행 중인 로그인을 가리키는 임시 ID다. 백엔드는 여기에 Telethon 클라이언트, `api_id`/`api_hash`, `phone_code_hash`를 묶어 메모리에 10분간 보관한다. 로그인에 성공하면 `api_id`/`api_hash`를 `users`에 저장하고, 실패하거나 10분이 지나면 메모리에서 지운다. `api_hash`는 어떤 응답에도 다시 내려주지 않는다.

**`POST /api/auth/sign-in`**
```json
// 요청
{ "login_id": "b3f1c2...", "code": "12345" }
// 응답 200 (쿠키 발급)
{ "user": { "id": 1, "display_name": "홍길동" } }
// 2단계 인증이 걸려 있으면 401 PASSWORD_REQUIRED
```

**`POST /api/auth/password`**
```json
// 요청
{ "login_id": "b3f1c2...", "password": "..." }
// 응답 200: sign-in 성공 응답과 같음
```

**`POST /api/auth/logout`** → 204. 텔레그램 세션을 끊고 DB에서 지운다.

### 7.2 내 정보

**`GET /api/me`** → 페이지를 새로 열 때 로그인 상태 확인용
```json
{ "user": { "id": 1, "display_name": "홍길동" } }
```

### 7.3 채팅방

**`GET /api/chats?q=검색어`** → 1:1 채팅방 목록, 최근 대화 순
```json
[
  { "chat_id": 123456789, "name": "김철수", "last_message_at": "2026-11-14T01:20:00Z",
    "enabled": true, "reply_delay_sec": 30, "ai_instructions": "회의 중이라고 안내",
    "fallback_text": "나중에 연락드릴게요.", "current_session_id": 7, "last_error": null,
    "analysis_status": "running", "analysis_started_at": "2026-11-14T01:00:00Z" }
]
```

- `analysis_status`: 말투·기억 분석 상태. 켜져 있을 때만 값이 있고 꺼져 있으면 `null`.
  - `running`: 분석 중. 이 동안 들어온 메시지의 답장은 분석이 끝날 때까지 미룬다(6.2)
  - `ready`: 분석 완료. 분석 결과로 답한다
  - `failed`: 분석 실패. 기본 답장으로 답하고, 사유는 `last_error`에 남는다
- `analysis_started_at`: 분석을 시작한 시각(UTC). `running`일 때만 값이 있고 나머지는 `null`. 화면에서 경과 시간을 보여 줄 때 쓴다.

**`PUT /api/chats/{chat_id}/auto-reply`**
```json
// 요청 (바꿀 필드만 보내도 됨)
{ "enabled": true, "reply_delay_sec": 60, "ai_instructions": "...", "fallback_text": "..." }
// 응답 200: 위 목록의 항목 하나와 같은 형식
```
`reply_delay_sec`이 5~120 밖이면 422. 켜면 응답의 `analysis_status`는 `running`이다.

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
| `/` | 메인(소개) 페이지: 캐릭터, 서비스 소개, "로그인" 버튼(`/login`으로 이동). 로그인 상태면 `/chats`로 이동 | `/me` |
| `/login` | `api_id`·`api_hash`·전화번호 → 인증 코드 → (필요 시) 2FA 비밀번호, 한 페이지에서 단계 전환. 첫 단계에 my.telegram.org 발급 안내 링크 | `/auth/*` |
| `/chats` | 1:1 채팅방 목록: 이름, 마지막 대화 시각, on/off 토글, 설정 버튼(대기 시간 슬라이더 5~120초, AI 지침, 대체 문구), 오류 표시(`last_error`), 분석 중 진행 표시(`analysis_status`, 경과 시간), 검색창 | `/chats` |
| `/chats/:chatId/sessions` | 세션 목록(시작·종료 시각, 메시지 수, AI 답장 수), 대화 미리 보기, 형식별 다운로드 버튼 | `/chats/{id}/sessions`, `/sessions/*` |
| `/settings` | 로그아웃 | `/auth/logout` |

- 로그인에 성공하면 바로 `/chats`로 이동한다.
- 앱 시작 시 `GET /api/me`로 로그인 상태를 확인한다. 로그인이 필요한 화면에서 401이면 `/login`으로 보낸다.
- 모든 화면 위에 로고와 서비스명("분신으로 자동답장")이 있는 고정 상단 바를 둔다.
- 켜져 있는 채팅방의 답장 상태는 `/chats`를 10초마다 다시 불러와 갱신한다. 분석 중(`running`)인 채팅방이 있으면 3초마다 불러온다. 실시간 알림(WebSocket)은 해커톤 범위에서 제외한다.

## 9. 보안과 운영 주의사항

- **Telethon 세션은 계정 전체 권한과 같다.** 유출되면 누구나 그 계정으로 메시지를 읽고 보낼 수 있다. 세션과 텔레그램 `api_hash`는 Fernet으로 암호화해 저장하고, 암호화 키(`ENCRYPTION_KEY`)는 `.env`에 DB와 분리해 둔다. `.gitignore`에는 이미 `.env`, `*.session`, `*.db`가 들어 있다.
- **로컬에서만 연다.** 백엔드는 `127.0.0.1:8080`에만 바인딩한다(`uvicorn --host 127.0.0.1 --port 8080`). 같은 네트워크의 다른 기기에서 접속해야 하면 그때 HTTPS를 적용한다.
- **GPU 서버 연결**: vLLM은 GPU 서버의 `127.0.0.1`에만 열고, 백엔드 PC에서 SSH 터널로만 접속한다(3.4). 요청과 대화 내용은 SSH로 암호화되어 인터넷을 지나간다. vLLM에 `--api-key`가 없어서 `--host 0.0.0.0`으로 외부에 열면 주소를 아는 누구나 GPU를 쓸 수 있다. 반드시 `127.0.0.1`로 띄운다. SSH 비밀번호는 저장소, `.env`, 로그에 남기지 않는다.
- **대화 원문 파일**: 자동 답장이 켜져 있는 동안 `backend/data/<user_id>/<chat_id>/`에 대화 원문(최대 1000개)과 분석 결과가 평문 파일로 남는다. `.gitignore`로 커밋에서 빠지고, 끄거나 로그아웃하면 지운다. 이 파일들을 공유하지 않는다.
- **사용자 간 데이터 분리**: 모든 조회에 `user_id` 조건을 건다. 남의 ID로 요청하면 404가 나오는지 확인한다.
- **AI 답장의 위험**: AI가 사용자 대신 약속을 하거나 사실과 다른 말을 할 수 있다. 3.4의 기본 지침으로 줄이고, 기록에 AI 답장을 구분해 표시한다.
- **로그인 시도 제한**: 같은 전화번호로 인증 코드를 짧은 간격으로 반복 요청하면 텔레그램이 계정을 일시 제한한다. 백엔드에서 1분에 1회로 막는다.
- **FloodWait 처리**: 텔레그램이 `FloodWaitError`를 주면 지정된 시간만큼 기다린 뒤 재시도하고, 프론트에는 `FLOOD_WAIT`로 알린다.
- **텔레그램 이용약관**: 사용자 계정 자동화는 스팸으로 판단되면 계정이 정지될 수 있다. 자동 답장은 본인이 켠 1:1 채팅방에만, 상대 메시지에 대한 응답으로만 보낸다. 시연은 팀원끼리의 대화로 한다.
- **시간대**: DB와 API는 UTC, 화면과 추출 파일만 KST.

### 백엔드 `.env` 항목

```
ENCRYPTION_KEY=...          # Fernet.generate_key()로 생성
LLM_BASE_URL=http://127.0.0.1:8000   # SSH 터널의 로컬 주소 (/v1 앞까지)
LLM_MODEL=...               # vLLM의 --served-model-name 값
LLM_TIMEOUT_SEC=30
```

텔레그램 `api_id`/`api_hash`는 `.env`에 넣지 않는다. 사용자가 화면에서 입력한다.

## 10. 구현 순서 (프론트·백엔드 병렬)

| 단계 | 백엔드 | 프론트엔드 |
|---|---|---|
| 0 | 이 문서의 7장 API 형식 확정 (함께) | |
| 1 | FastAPI 뼈대, DB 모델, Fernet 암호화 | Vite + React 프로젝트, 라우팅, 7장 형식의 목 데이터 |
| 2 | 웹 로그인 (send-code에 사용자별 `api_id`/`api_hash` / sign-in / password), `ClientManager` | 로그인 화면 3단계 |
| 3 | (삭제: LLM API 키를 쓰지 않음) | |
| 4 | 채팅방 목록 (`send.py`의 `iter_dialogs` 재사용, `dialog.is_user`로 필터), on/off와 세션 생성·종료 | 채팅방 목록, 토글, 설정 모달 |
| 5 | 지연 답장과 메시지 로그 (처음엔 고정 문구로 확인) → `generate_reply`에 GPU 서버 연결 | 오류 표시, 10초 주기 갱신 |
| 6 | 세션 목록, 미리 보기, 추출 (JSON → CSV → TXT) | 세션 화면, 다운로드 |
| 7 | 목 데이터를 실제 API로 교체하고 통합 테스트, 시연 시나리오 점검 (함께) | |

## 11. 결정 사항

| 항목 | 결정 |
|---|---|
| 대기 시간 | 사용자가 채팅방마다 5~120초 중에서 고름. 기본 30초 |
| 사용자가 직접 답하면 | 대기 중인 AI 답장 취소 |
| LLM | 개인 클라우드 GPU 서버의 vLLM, OpenAI 호환 API로 호출 |
| GPU 서버 주소·모델 | 모든 사용자 공통, 백엔드 `.env`에 설정 |
| 텔레그램 `api_id`/`api_hash` | 사용자가 로그인할 때마다 자기 값을 입력. 로그인 중에는 DB에 암호화 저장, 로그아웃 시 삭제 |
| LLM 접속 | API 키 없음. GPU 서버 vLLM에 SSH 터널(비밀번호 로그인)로 접속 |
| 실행 환경 | 로컬 PC (프론트 `:5173`, 백엔드 `:8080`, vLLM SSH 터널 `:8000`) |
| 구현 분담 | 프론트 React, 백엔드 Python(FastAPI) |

## 12. GPU 서버 담당자에게 받아야 할 것

- SSH 접속 정보: 서버 주소, 사용자 이름, 비밀번호 (저장소에 적지 않고 직접 전달받는다)
- `LLM_MODEL`: `--served-model-name` 값 (현재 `qwen3.8-27b`)
- 동시에 몇 개의 요청까지 처리할 수 있는지 (여러 사용자의 답장이 겹칠 때 확인용)
