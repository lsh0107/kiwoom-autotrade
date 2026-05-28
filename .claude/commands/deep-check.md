# Deep Check

작업 완료 보고 전에 `.claude/rules/deep-work.md` 기준으로 self-review 를 수행한다.

## 실행 지시

다음을 확인하고 PASS / FAIL 로 보고한다.

1. Scope
   - 사용자 요청을 빠뜨린 항목이 없는가?
   - 이번 작업에서 하지 않기로 한 범위를 침범하지 않았는가?

2. Git / Files
   - 현재 branch 와 `git status` 를 확인했는가?
   - 변경 파일 목록이 의도한 범위와 일치하는가?
   - 기존 사용자 변경 / untracked 산출물을 건드리지 않았는가?

3. Safety
   - trading / order / auth / DB / broker / live_trader 영향이 있는가?
   - fake success / fake balance / fake order fallback 이 생기지 않았는가?
   - mock 검증을 live 검증처럼 표현하지 않았는가?
   - PR E2 / AI hedge live consumption 금지선을 침범하지 않았는가?

4. Verification
   - 필요한 테스트 / lint / CI 를 실행했는가?
   - 실행하지 않았다면 이유가 타당한가?
   - 문서 변경이면 링크 / 경로 / diff 검토를 했는가?

5. Report
   - "완료"라고 말할 수 있는가, 아니면 "구현 완료, 검증 대기"인가?
   - 남은 위험과 검증 한계를 명시했는가?

출력 형식:

```text
## Deep Check
- Scope: PASS/FAIL — ...
- Git/Files: PASS/FAIL — ...
- Safety: PASS/FAIL — ...
- Verification: PASS/FAIL — ...
- Report readiness: PASS/FAIL — ...

결론: DONE / NOT DONE
```
