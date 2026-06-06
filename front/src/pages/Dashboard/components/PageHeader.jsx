export default function PageHeader({ latestCheckedAt }) {
  return (
    <section className="page-head">
      <div>
        <h1>지하철역 상수도 위험도 전체 현황</h1>
        <p className="head-desc">수도사업소, 호선, 위험도 기준으로 역별 이상징후를 한 화면에서 확인합니다.</p>
      </div>
      <div className="head-status">
        <span>데이터 기준</span>
        <strong>{latestCheckedAt ?? "수집 대기"}</strong>
      </div>
    </section>
  );
}
