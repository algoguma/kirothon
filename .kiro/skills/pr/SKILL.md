---
name: pr
description: 현재 작업 브랜치를 main 기준으로 정리하고 push한 뒤 GitHub PR을 만든다. 사용자가 PR을 올려 달라고 하거나 /pr을 실행했을 때 사용한다.
---

# PR 만들기

`.kiro/steering/git-workflow.md` 규칙을 따른다. 추가 설명: $ARGUMENTS

1. `git status`와 `git branch --show-current`로 상태를 확인한다.
   - 현재 브랜치가 `main`이면 멈추고, 규칙에 맞는 브랜치 이름을 제안한다.
   - 커밋하지 않은 변경이 있으면 파일 목록을 보여주고 어떤 파일을 커밋할지 묻는다.
2. 커밋할 파일을 지정해서 `git add <파일>` 후 `git diff --staged`를 검토한다. `.env`, `*.session`, `*.db`, 키 문자열이 있으면 멈추고 알린다.
3. `<type>(<scope>): <한국어 설명>` 형식으로 커밋한다.
4. `git fetch origin` 후 `git rebase origin/main`. 충돌이 나면 충돌 파일과 양쪽 내용을 보여주고 해결 방향을 사용자와 정한다.
5. 프로젝트에 린트나 테스트가 있으면 변경한 영역만 실행한다 (backend: `ruff check`, frontend: `npm run lint`, `npm run build`).
6. `git push -u origin <브랜치>`. 푸시 전에 사용자에게 확인받는다.
7. PR 생성:
   - `gh`가 있으면 `gh pr create --base main --title "<커밋 형식 제목>" --body-file <임시 파일>`로 만든다. 본문은 `.github/pull_request_template.md`를 채운다.
   - `gh`가 없으면 `https://github.com/algoguma/kirothon/compare/main...<브랜치>?expand=1` 링크와 채운 본문을 출력한다.
8. 리뷰어는 지정하지 않는다. 다른 사람 소유 경로(AGENTS.md)나 공유 파일을 바꿨으면 알려야 할 소유자를 알려준다.
