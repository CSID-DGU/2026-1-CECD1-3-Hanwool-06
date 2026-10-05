import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import { EmptyNote, SectionTitle } from "../../Detail/ui.jsx";
import { detailHref, signedPct, ton } from "../../Detail/data.js";

export default function StationTable({ stations, billingOnly = false, actions }) {
  return (
    <section className="table-panel">
      <SectionTitle as="h2" right={actions}>
        {billingOnly ? "청구 전용 계량기" : "계량기 목록"} <span className="count">{stations.length}개</span>
      </SectionTitle>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>역명</th>
              <th>호선</th>
              <th>영업사업소</th>
              {!billingOnly && <><th>위험도</th><th className="num">일 사용량</th><th className="num">예측 대비</th></>}
              <th>{billingOnly ? "최근 청구월" : "기준일"}</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id}>
                <td>
                  <a className="station-link" href={detailHref(station.id)}>{station.name}</a>
                  <small>{station.displayName} {station.customerNo}</small>
                </td>
                <td><LineBadges lines={station.lines} /></td>
                <td>{station.office}</td>
                {!billingOnly && <>
                  <td>
                    <RiskBadge risk={station.risk} />
                    {station.riskDetail && <small>{station.riskDetail}</small>}
                  </td>
                  <td className="num">{ton(station.usage)} 톤</td>
                  <td className="num">{signedPct(station.delta)}</td>
                </>}
                <td>{billingOnly ? station.latestBillMonth || "청구서 없음" : <>사용량 {station.dailyDate || "없음"}<small>분석 {station.riskDate || "대기"}</small></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {stations.length === 0 ? <EmptyNote>조건에 맞는 계량기가 없습니다.</EmptyNote> : null}
      </div>
    </section>
  );
}
