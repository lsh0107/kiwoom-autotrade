# 에이전트 작업 기록 규칙 (MANDATORY)

**이 규칙은 모든 에이전트(서브에이전트 포함)가 반드시 따라야 한다.**

## 작업 기록 프로토콜

### 언제 기록하나?
- **작은 덩어리 하나 완료할 때마다** 즉시 기록
- "작은 덩어리" = 파일 1~3개 생성/수정, 또는 하나의 기능 단위 완성
- 예: "DB 모델 User 작성 완료", "인증 라우터 구현 완료", "Docker Compose 작성 완료"

### 어디에 기록하나?
- 파일: `.claude/memory/sessions/YYYY-MM-DD.md` (당일 날짜)
- 기존 내용이 있으면 **append** (덮어쓰기 금지)

### 기록 형식 (반드시 이 형식 준수)
```markdown
### HH:MM - [에이전트 역할] [작업 제목]
- **에이전트**: 백엔드 / 프론트엔드 / 데브옵스 / QA / 리드
- **수행**: 무엇을 했는지 (구체적으로)
- **생성 파일**: 새로 만든 파일 경로
- **수정 파일**: 수정한 파일 경로
- **결정**: 내린 설계/기술 결정 (있으면)
- **TODO**: 이 작업에서 파생된 남은 할 일
- **이슈**: 발견한 문제점이나 주의사항 (있으면)
```

### 예시
```markdown
### 14:30 - [백엔드] DB 모델 구현 (User, Invite)
- **에이전트**: 백엔드
- **수행**: SQLAlchemy 2.0 async 모델 작성. User(UUID PK, email unique, role), Invite(code unique, expires_at)
- **생성 파일**: src/models/base.py, src/models/user.py, src/models/invite.py
- **수정 파일**: src/models/__init__.py
- **결정**: TimestampMixin을 MappedAsDataclass 대신 일반 Mixin으로 구현 (SQLAlchemy async 호환성)
- **TODO**: Order, Strategy 모델 구현 필요
- **이슈**: 없음
```

## 절대 규칙
1. 기록 없이 다음 작업으로 넘어가지 마라
2. 파일 경로는 프로젝트 루트 기준 상대 경로로 작성
3. 날짜 파일이 없으면 새로 생성
4. 기존 내용 절대 삭제/덮어쓰기 금지, append만
5. 현재 시각은 `date +%H:%M` 명령으로 확인
