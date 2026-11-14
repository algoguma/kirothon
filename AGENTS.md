# AGENTS.md

텔레그램 1:1 채팅방별 AI 자동 답장 서비스. 전체 명세는 `docs/auto-reply-spec.md`가 기준이다.

## 팀 역할

| 역할 | 담당 | 소유 경로 | 브랜치 접두사 |
|---|---|---|---|
| Frontend | React 화면 전체, mock 데이터, API 연동 | `frontend/` | `feature/fe-` |
| Backend | FastAPI, DB, 암호화, 웹 로그인, `ClientManager`, 채팅방·세션·추출 API, 자동 답장 디바운스 처리 | `backend/` (`backend/app/ai/` 제외) | `feature/be-` |
| AI | `backend/app/ai/` 전체: 답장 생성, 프롬프트(기본 지침), 대화 기록 → 메시지 변환, 키 확인, vLLM 서버 연결과 운영 | `backend/app/ai/` | `feature/ai-` |

- 자기 소유 경로 밖의 파일을 고쳐야 하면 머지 전에 해당 소유자에게 알린다.
- 공유 파일(`docs/auto-reply-spec.md`, `backend/requirements.txt`, `frontend/package.json`, `.kiro/`)은 변경 이유를 PR 본문에 적는다.

## 역할 간 계약

- **Frontend ↔ Backend**: `docs/auto-reply-spec.md` 7장(API 명세). 바꿀 때는 명세 PR을 먼저 머지한다.
- **Backend ↔ AI**: `backend/app/ai/__init__.py`에서 아래 두 함수만 노출한다. 백엔드는 이 함수만 호출하고 내부 구현에 의존하지 않는다.
  ```python
  async def generate_reply(api_key: str, history: list[ChatMessage], instructions: str) -> str
      # 실패·시간 초과 시 LLMError를 던진다. 대체 문구 처리는 백엔드가 한다.
  async def verify_api_key(api_key: str) -> None
      # GET {LLM_BASE_URL}/v1/models. 실패 시 LLMError.
  ```
  `ChatMessage`는 `sender_name`, `text`, `date`, `is_outgoing`을 가진 dataclass다. 시그니처를 바꾸려면 Backend와 AI가 함께 합의한다.

## 에이전트 작업 규칙

- 명세와 다르게 구현해야 하면 코드보다 명세 수정 제안을 먼저 한다.
- `.env`, `*.session`, `*.db`, API 키, Telethon 세션 문자열은 읽어서 출력하거나 커밋하지 않는다.
- 커밋, 브랜치, PR 규칙은 `.kiro/steering/git-workflow.md`를 따른다.
