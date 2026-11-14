---
inclusion: always
---

# 코딩 규칙

## 공통
- 식별자와 코드 주석은 영어, 사용자에게 보이는 문구는 한국어.
- 시각은 DB와 API에서 UTC(ISO 8601, `Z`), 화면과 추출 파일에서만 KST.
- 해커톤이므로 명세 범위 밖 기능, 추상화, 일반화를 미리 만들지 않는다.

## Python (backend)
- 타입 힌트 필수. 요청·응답은 Pydantic 모델로 정의하고 필드명은 명세 7장과 같게 snake_case.
- 오류는 명세 7장의 형식 `{"error": {"code", "message"}}`으로만 반환한다. 공통 예외 핸들러 하나에서 변환한다.
- 모든 DB 조회에 `user_id` 조건을 건다. 남의 리소스는 404.
- 포맷과 린트는 `ruff format`, `ruff check`.

## TypeScript (frontend)
- `strict` 모드. API 타입은 `src/api/types.ts` 한 곳에 명세 7장과 같은 이름으로 정의한다.
- API 호출은 `src/api/` 모듈을 통해서만 한다. mock과 실제 API를 환경변수(`VITE_USE_MOCK`)로 전환한다.
- 포맷과 린트는 프로젝트 생성 시 정한 eslint/prettier 설정을 따른다.
