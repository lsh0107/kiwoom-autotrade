# GitHub 워크플로우 규칙 (MANDATORY)

## 브랜치 전략
```
claude(base) → feat/* → dev(PR, squash) → main(PR, merge commit)
```
- main/dev 직접 push 금지
- claude 브랜치는 main과 항상 싱크

## PR 생성 흐름
1. `git push -u origin feat/xxx`
2. `gh pr create --base dev`
3. `gh pr checks <PR번호>` 또는 `gh run list --branch feat/xxx`로 Actions 결과 확인
4. Actions 전체 통과 확인 후 머지 (실패 시 즉시 수정 → re-push)

## dev → main 머지
1. `gh pr create --base main --head dev`
2. Actions 전체 통과 확인
3. merge commit 방식으로 머지
4. `git checkout claude && git merge main` 싱크

## GitHub Actions 확인 (MANDATORY)
- PR 생성 후 **반드시** `gh pr checks`로 결과 확인
- 확인 없이 머지 금지
- Actions 실패 시 즉시 원인 파악 → 수정 → push
- skipping은 해당 언어/파일 변경 없음으로 정상

## 커밋 컨벤션
- `feat(모듈): 한글 설명` (feat/fix/refactor/test/docs/chore/ci)
- `git add .` / `git add -A` 금지 — 논리적 단위로 스테이징
- Co-Authored-By, Generated with Claude Code 등 자동 생성 문구 금지
- description은 구체적으로, 읽기 편하게
