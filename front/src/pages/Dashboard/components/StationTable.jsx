import { formatNumber } from "../utils.js";
import EmptyState from "./EmptyState.jsx";
import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import SectionTitle from "./SectionTitle.jsx";

export default function StationTable({ stations }) {
  return (
    <section className="table-panel">
      <SectionTitle title="역별 관제 목록" right={`${stations.length}개 역`} />
      <div className="table-wrap">
        <table className="station-table">
          <thead>
            <tr>
              <th>역명</th>
              <th>호선</th>
              <th>수도사업소</th>
              <th>위험도</th>
              <th>일 사용량</th>
              <th>예측대비</th>
              <th>수집시각</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id}>
                <td>
                  <strong>{station.name}</strong>
                  <small>{station.customerNo}</small>
                </td>
                <td>
                  <LineBadges lines={station.lines} />
                </td>
                <td>{station.office}</td>
                <td>
                  <RiskBadge risk={station.risk} />
                </td>
                <td>{formatNumber(station.usage)} 톤</td>
                <td className={station.delta >= 10 ? "delta-up" : station.delta < 0 ? "delta-down" : ""}>
                  {station.delta > 0 ? "+" : ""}
                  {station.delta}%
                </td>
                <td>{station.checkedAt.slice(5)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {stations.length === 0 ? <EmptyState text="조건에 맞는 관제 대상이 없습니다. 필터를 조정해 주세요." /> : null}
      </div>
    </section>
  );
}
