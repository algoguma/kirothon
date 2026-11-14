# kirothon

텔레그램 1:1 채팅방별 AI 자동 답장 서비스 (Kirothon 해커톤).

- 명세: [docs/auto-reply-spec.md](docs/auto-reply-spec.md)
- 팀 역할과 작업 규칙: [AGENTS.md](AGENTS.md)

## 구성

| 경로 | 내용 | 실행 |
|---|---|---|
| `frontend/` | React + Vite + TypeScript | `http://localhost:5173` |
| `backend/` | Python FastAPI + Telethon | `http://127.0.0.1:8000` |

실행 방법은 각 프로젝트가 만들어지면 추가한다.

## Kiro 사용

이 저장소는 Kiro 설정(`.kiro/`)을 공유한다. clone 후 저장소 루트에서 `kiro-cli`를 실행하면 `team` 에이전트와 `claude-opus-5.5` 모델이 자동으로 적용된다. 모델을 바꾸지 않는다.

- PR 만들기: 세션에서 `/pr`
- PR 리뷰: `kiro-cli --agent reviewer`
