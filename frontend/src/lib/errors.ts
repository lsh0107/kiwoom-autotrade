/** API 에러 코드 → 사용자 메시지 매핑 중앙화 */

export const ERROR_MESSAGES: Record<string, string> = {
  NO_CREDENTIALS: "등록된 API 키가 없습니다. 설정에서 먼저 등록해주세요.",
  BROKER_RATE_LIMIT: "API 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
  BROKER_AUTH_ERROR: "키움 API 인증 오류. 설정에서 API 키를 확인해주세요.",
  BROKER_ERROR: "잘못된 종목코드입니다. 6자리 숫자를 확인해주세요.",
  NOT_FOUND: "요청한 정보를 찾을 수 없습니다.",
  UNKNOWN: "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
};

/** 에러 코드로 사용자 메시지 반환 (없으면 fallback 또는 UNKNOWN) */
export function getErrorMessage(code: string, fallback?: string): string {
  return ERROR_MESSAGES[code] ?? fallback ?? ERROR_MESSAGES.UNKNOWN;
}
