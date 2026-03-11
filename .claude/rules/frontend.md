---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.css"
---

# 프론트엔드 코딩 규칙

## 도구
- Next.js 16+ (App Router) / React 19 / TypeScript strict / Tailwind v4 / shadcn/ui (new-york)
- 데이터: TanStack Query v5 / 폼: React Hook Form + Zod / 차트: Recharts
- 테스트: Vitest + React Testing Library / 린트: ESLint (next/core-web-vitals)

## 폴더 구조
```
frontend/src/
├── app/(authenticated)/   # 인증 필요 페이지
├── app/login, register/   # 공개 페이지
├── components/ui/         # shadcn/ui 컴포넌트 (수정 금지)
├── components/            # 커스텀 컴포넌트
├── hooks/queries/         # useQuery 훅 (1파일 1훅)
├── hooks/mutations/       # useMutation 훅 (1파일 1훅)
├── lib/                   # api.ts, constants.ts, errors.ts, format.ts
├── types/                 # api.ts (백엔드 응답 타입)
└── middleware.ts           # 인증 미들웨어
```

## 스타일
- 변수/함수: `camelCase`, 컴포넌트: `PascalCase`, 상수: `UPPER_SNAKE_CASE`
- UI 텍스트/주석 한글, 변수명 영어
- 손익 색상: 수익=빨강(`text-red-600`), 손실=파랑(`text-blue-600`)

## 페이지 컴포넌트 패턴
```tsx
"use client";                          // 1. 지시어
import { useState } from "react";      // 2. React/Next.js
import { useBalance } from "@/hooks/queries/use-balance";  // 3. 커스텀 훅
import { formatKRW } from "@/lib/format";                  // 4. 유틸
import type { AccountBalance } from "@/types/api";         // 5. 타입
import { Card, ... } from "@/components/ui/card";          // 6. UI
import { Wallet } from "lucide-react";                     // 7. 아이콘
import { toast } from "sonner";                            // 8. 외부

function PageSkeleton() { ... }        // 내부 헬퍼 먼저
function ErrorState() { ... }

export default function Page() {       // 메인 컴포넌트
  const { data, isLoading, error } = useBalance();
  if (isLoading) return <PageSkeleton />;
  // ...
}
```

## 데이터 페칭
- API 경로/쿼리 키: `lib/constants.ts`에 집중 (`API_PATHS`, `QUERY_KEYS`)
- 쿼리 훅: `hooks/queries/use-*.ts` — `useQuery({ queryKey, queryFn, staleTime: 30_000 })`
- 뮤테이션 훅: `hooks/mutations/use-*.ts` — `onSuccess`에 toast, `onError`에 `getErrorMessage()`
- API 클라이언트: `lib/api.ts` — GET 10초 캐시, `credentials: "include"` (httpOnly cookie)

## 폼
- Zod 스키마 정의 → `zodResolver` → `useForm<T>` → `form.handleSubmit`
- 한국 주식 가격: `z.number().int()` + `step="1"` (정수 강제)
- 주문 전 확인: AlertDialog 필수

## 에러 처리
- `ApiClientError(status, code, message)` → `getErrorMessage(code)` → `toast.error()`
- `lib/errors.ts`에 에러 코드별 한글 메시지 매핑
- 기술 용어 노출 금지, 사용자 행동 안내 포함

## 인증
- httpOnly cookie (access_token + refresh_token)
- `middleware.ts`: 1차 차단 (쿠키 유무)
- `use-auth.ts`: 2차 검증 (토큰 유효성 + 자동 refresh)
- 인증 실패 시 `logout()` 호출하여 쿠키 정리 후 `/login` 리다이렉트

## 테스트
- 스모크 테스트: 모든 페이지 크래시 없이 렌더링 확인
- Hook mock: `vi.mock()`, Query/Mutation mock 헬퍼 사용
- TestWrapper: `QueryClientProvider` 감싸기
