export const isCollectionActive = (job) => ["queued", "running"].includes(job?.status);
export const isCollectionFinished = (job) => ["success", "partial", "failed", "interrupted"].includes(job?.status);
export const collectionLabel = (status) => ({
  unverified: "연결 미확인", queued: "수집 예약", running: "수집 중", success: "수집 완료",
  partial: "일부 수집 완료", failed: "수집 실패", interrupted: "수집 중단", skipped: "수집 제외",
  access_required: "아리수 조회 권한 필요",
  empty: "조회 자료 없음", not_configured: "로그인 설정 미완료", configuration_required: "로그인 설정 미완료", no_data: "조회 자료 없음",
})[status] || "연결 미확인";

// The next queued job may become visible before the previous one is returned as latest.
export function collectionNeedsRefresh(previous, next) {
  if (!previous) return false;
  return Boolean(
    isCollectionActive(previous.running) && previous.running.id !== next.running?.id
    || isCollectionFinished(next.latest) && (next.latest.id !== previous.latest?.id || !isCollectionFinished(previous.latest))
  );
}

export function collectionTime(value) {
  if (!value) return "기록 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "시각 확인 필요";
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(date);
}

export function meterCollectionState(meter, record) {
  if (meter.deleted_at) return "삭제 보관";
  if (meter.provider !== "arisu") return "자동 수집 미지원";
  if (record?.connection_verified) return "연결 확인";
  return "연결 미확인";
}
