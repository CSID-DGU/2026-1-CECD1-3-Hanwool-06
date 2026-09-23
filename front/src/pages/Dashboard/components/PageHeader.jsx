export default function PageHeader({ status }) {
  const basis = status.reference_date;
  const dateText = (value) => value ? String(value).replace("T", " ").slice(0, 16) : "수집 전";
  return <section className="page-head">
    <div><span className="eyebrow">WATER MONITORING</span><h1>상수도 관제 현황</h1>
      <p className="head-desc">담당 사업소의 계량기 상태와 이상징후를 확인합니다.</p></div>
    <div className="head-status"><span>{status.latest_risk ? "위험도 분석 기준" : "자료 기준"}</span><strong>{basis || "자료 수집 대기"}</strong>
      <span className="head-collected">사용량 {dateText(status.latest_usage)} · 승하차 {dateText(status.latest_ridership)}</span>
      <span className="head-collected">위험도 {dateText(status.latest_risk)} · 화면은 1분마다 확인</span></div>
  </section>;
}
