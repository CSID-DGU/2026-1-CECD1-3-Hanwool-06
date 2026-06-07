const KDOW = ["일", "월", "화", "수", "목", "금", "토"];

// 수집시각(checkedAt, 오늘 아침)으로부터 데이터 기준일(D-1=어제)과 수집 시각을 만든다.
// 디테일 화면의 "6/7 (일) 기준" 과 같은 날짜 체계로 맞추기 위함.
function basisFromCheckedAt(checkedAt) {
  if (!checkedAt) return null;
  const [datePart, timePart] = checkedAt.split(" ");
  const [y, m, d] = datePart.split("-").map(Number);
  const collected = new Date(y, m - 1, d);
  const basis = new Date(collected);
  basis.setDate(basis.getDate() - 1);
  const md = (dt) => `${dt.getMonth() + 1}/${dt.getDate()}`;
  return {
    기준일: `${md(basis)} (${KDOW[basis.getDay()]})`,
    수집: `${md(collected)} ${timePart ?? ""}`.trim(),
  };
}

export default function PageHeader({ latestCheckedAt }) {
  const basis = basisFromCheckedAt(latestCheckedAt);
  return (
    <section className="page-head">
      <div>
        <h1>지하철역 상수도 위험도 전체 현황</h1>
        <p className="head-desc">영업사업소, 호선, 위험도 기준으로 역별 이상징후를 한 화면에서 확인합니다.</p>
      </div>
      <div className="head-status">
        <span>데이터 기준</span>
        <strong>{basis ? basis.기준일 : "수집 대기"}</strong>
        {basis ? <span className="head-collected">최종 수집 {basis.수집}</span> : null}
      </div>
    </section>
  );
}
