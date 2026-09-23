export function formatNumber(value) {
  return Number.isFinite(value) ? new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value) : "—";
}
