// 화면 제목, 현황 한 줄, 자료별 기준일.
export default function PageHeader({ status, daily, alerts, warnings }) {
  const day = (value) => (value ? String(value).slice(0, 10) : "없음");
  return (
    <section className="page-head">
      <div>
        <h1>상수도 관제 현황</h1>
        <p className="head-summary">
          {daily
            ? <>일일 관제 계량기 {daily}개 가운데 <strong className={alerts ? "is-alert" : ""}>경고 {alerts}건</strong>, <strong className={warnings ? "is-warn" : ""}>주의 {warnings}건</strong>입니다.</>
            : "일일 사용량을 수집하는 계량기가 아직 없습니다."}
        </p>
      </div>
      <div className="data-dates">
        <span>자료 기준일</span>
        <dl>
          <div><dt>위험도 분석</dt><dd>{day(status.latest_risk)}</dd></div>
          <div><dt>사용량</dt><dd>{day(status.latest_usage)}</dd></div>
          <div><dt>승하차</dt><dd>{day(status.latest_ridership)}</dd></div>
        </dl>
      </div>
    </section>
  );
}
