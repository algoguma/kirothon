---
inclusion: always
---

# Git 작업 규칙 (3인 팀)

## 브랜치
- 장기 브랜치는 `main` 하나. `main`에 직접 커밋하거나 push하지 않는다.
- 작업 브랜치: `feature/fe-<내용>`, `feature/be-<내용>`, `feature/ai-<내용>`, `fix/<내용>`, `chore/<내용>`, `docs/<내용>`.
- 브랜치는 짧게 쓰고(1~2시간 분량), 머지 후 삭제한다.
- 다른 사람의 브랜치에 커밋하지 않는다.

## 커밋
- 형식: `<type>(<scope>): <한국어 설명>`
  - type: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`
  - scope: `fe`, `be`, `ai`, `spec`, `kiro`
  - 예: `feat(be): 인증 코드 요청 API 추가`
- `git add .`이나 `git add -A`를 쓰지 않는다. 파일을 지정해서 stage한다.
- 커밋 전에 `git diff --staged`로 `.env`, 세션, DB 파일, 키가 없는지 확인한다.

## PR
- PR 전에 `git fetch origin` 후 `git rebase origin/main`. 충돌은 자기 브랜치에서 해결한다.
- PR은 작게(변경 300줄 안팎), 제목은 커밋 형식과 같게 쓴다. 본문은 `.github/pull_request_template.md`를 채운다.
- 승인 1명 이상 후 **Squash merge**. 리뷰 요청을 받으면 10분 안에 응답한다.
- API 형식(명세 7장)이나 Backend↔AI 함수 시그니처를 바꾸는 PR은 `docs(spec)` PR로 먼저 머지하고 구현은 그다음에 한다.
- `.kiro/`, `AGENTS.md` 변경은 기능 PR에 섞지 않고 `chore(kiro)` PR로 따로 올린다.

## 금지
- `git push --force`, `git reset --hard`, `git rebase`로 이미 push된 공유 이력 변경, `main` 직접 push.
- Kiro 모델 변경. 팀 전원이 `claude-opus-5.5`를 쓴다.
