/** 공통 포맷팅 유틸리티 */

/** 한국 원화 형식으로 숫자 포맷 (천 단위 구분) */
export function formatKRW(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

/** 숫자 포맷 (천 단위 구분, 통화 아닌 수량용) */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

/** 백분율 포맷 (소수점 2자리) */
export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

/** 부호 포함 백분율 포맷 (+/-) */
export function formatSignedPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

/** 부호 포함 원화 포맷 (양수 시 + 접두사) */
export function formatSignedKRW(value: number): string {
  return `${value > 0 ? "+" : ""}₩${formatKRW(value)}`;
}

/** ISO 날짜 문자열을 "YYYY-MM-DD HH:mm" 형식으로 포맷 */
export function formatDate(isoString: string): string {
  const d = new Date(isoString);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** 날짜를 한국 로케일 날짜 형식으로 포맷 (등록일 등) */
export function formatLocalDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("ko-KR");
}
