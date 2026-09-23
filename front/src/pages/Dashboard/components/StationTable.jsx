import { formatNumber } from "../utils.js";
import EmptyState from "./EmptyState.jsx";
import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import SectionTitle from "./SectionTitle.jsx";
import { detailHref } from "../../Detail/data.js";

export default function StationTable({ stations, billingOnly = false }) {
  return (
    <section className="table-panel">
      <SectionTitle title={billingOnly ? "청구 전용 계량기 목록" : "계량기별 관제 목록"} right={`${stations.length}개 계량기`} />
      <div className="table-wrap">
        <table className="station-table">
          <thead>
            <tr>
              <th>역명</th>
              <th>호선</th>
              <th>영업사업소</th>
              <th>{billingOnly ? "제공 자료" : "위험도 · 상태"}</th>
              {!billingOnly && <><th>일 사용량</th><th>예측대비</th></>}
              <th>{billingOnly ? "최근 청구월" : "사용량 / 분석 기준일"}</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id}>
                <td>
                  <a className="station-link" href={detailHref(station.id)}><strong>{station.name}</strong></a>
                  <small>{station.displayName} · {station.customerNo}</small>
                </td>
                <td>
                  <LineBadges lines={station.lines} />
                </td>
                <td>{station.office}</td>
                <td>
                  <RiskBadge risk={station.risk} />
                  {station.riskDetail && <small>{station.riskDetail}</small>}
                </td>
                {!billingOnly && <><td>{formatNumber(station.usage)} 톤</td>
                <td className={station.delta >= 10 ? "delta-up" : station.delta < 0 ? "delta-down" : ""}>
                  {station.delta == null ? "—" : `${station.delta > 0 ? "+" : ""}${station.delta}%`}
                </td></>}
                <td>{billingOnly ? station.latestBillMonth || "청구자료 없음" : <><span>사용량 {station.dailyDate || "수집 전"}</span><small>분석 {station.riskDate || "분석 대기"}</small></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {stations.length === 0 ? <EmptyState text="조건에 맞는 관제 대상이 없습니다. 필터를 조정해 주세요." /> : null}
      </div>
    </section>
  );
}
