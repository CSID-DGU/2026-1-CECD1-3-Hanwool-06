import { useMemo, useState } from "react";
import { won, billGroundwater, billLabel, billNoticeNumber, billUsage, billWindow } from "./data";
import { EmptyNote, InfoTooltip, SectionTitle } from "./ui";
import LineChart from "./LineChart";
import { pdfUrl } from "../../api.js";
import FileLink from "../../components/FileLink.jsx";

// Authenticated bill records. Missing readings stay blank in the document and chart.
export default function Bill({ station, line }) {
  if (!line.bills?.length) return <EmptyNote>등록된 청구서가 없습니다. 첫 청구자료 수집 후 열람할 수 있습니다.</EmptyNote>;
  return <BillContent station={station} line={line} />;
}

function BillContent({ station, line }) {
  const bills = line.bills;
  const nz = (n) => (n == null ? "—" : won(n)); // 결측 칸은 "—"
  const keyOf = (b) => b.id || `${b.ym}-${billLabel(b)}`;
  const [selected, setSelected] = useState(keyOf(bills.at(-1)));
  const bill = bills.find((b) => keyOf(b) === selected) || bills.at(-1);
  const noticeNumber = billNoticeNumber(bill);
  const pdfFilename = `${station.역명}_${line.고객번호}_${bill.ym}_${bill.gubun || "정기분"}${noticeNumber ? `_${noticeNumber}` : ""}.pdf`;
  const comparisonBills = bills.filter((b) => (b.gubun || "정기분") === (bill.gubun || "정기분"));
  const usageOf = billUsage;
  const groundwater = billGroundwater(bill);
  const payment = bill.납부금액 ?? bill.부과금액 ?? null;
  const paymentLabel = bill.납부금액 != null ? "납부금액" : "부과금액";
  const additionalFees = ["계량기대금", "설치비", "연체금"].filter((key) => bill[key] != null);

  const years = useMemo(() => [...new Set(bills.map((b) => b.year))].sort(), [bills]);
  const monthsOfYear = useMemo(
    () => [...new Set(bills.filter((b) => b.year === bill.year).map((b) => b.month))].sort((a, b) => a - b),
    [bills, bill.year]
  );
  const onYear = (y) => {
    const inYear = bills.filter((b) => b.year === Number(y));
    setSelected(keyOf(inYear.at(-1)));
  };
  const onMonth = (m) => setSelected(keyOf(bills.find((b) => b.year === bill.year && b.month === Number(m))));

  // The selected month and its previous eleven calendar months.
  const window = billWindow(comparisonBills, bill.ym);
  const trend = {
    values: window.map(usageOf),
    labels: window.map((b) => b.ym.slice(2).replace("-", "/")),
  };

  // 최근 5년 동월 비교
  const YOY_N = 5;
  const mm = String(bill.month).padStart(2, "0");
  const yoyYears = Array.from({ length: YOY_N }, (_, k) => bill.year - (YOY_N - 1) + k);
  const yoyLabels = yoyYears.map((y) => `${String(y).slice(2)}/${mm}`);
  const yoyValues = yoyYears.map((y) => { const found = y === bill.year ? bill : comparisonBills.find((b) => b.year === y && b.month === bill.month); return found ? usageOf(found) : null; });
  const cur = usageOf(bill);
  const prevYearVal = yoyValues[YOY_N - 2];
  const dPrev = cur != null && prevYearVal ? Math.round(((cur - prevYearVal) / prevYearVal) * 100) : null;
  const histVals = yoyValues.slice(0, YOY_N - 1).filter((v) => v != null);
  const avgHist = histVals.length ? histVals.reduce((a, b) => a + b, 0) / histVals.length : null;
  const dAvg = cur != null && avgHist ? Math.round(((cur - avgHist) / avgHist) * 100) : null;

  // 계절별 추이: 청구(납기) 월이 역마다 홀/짝으로 갈려서 실제 데이터에서 추출(하드코딩 X). 월별 전기간 평균
  const billMonths = [...new Set(comparisonBills.map((b) => b.month))].sort((a, b) => a - b);
  const seasonValues = billMonths.map((m) => {
    const vs = comparisonBills.filter((b) => b.month === m).map(usageOf).filter((v) => v != null);
    return vs.length ? Math.round(vs.reduce((a, b) => a + b, 0) / vs.length) : null;
  });
  const seasonLabels = billMonths.map((m) => String(m));
  const seasonYrs = comparisonBills.map((b) => b.year);
  const seasonYmin = Math.min(...seasonYrs);
  const seasonYmax = Math.max(...seasonYrs);
  const seasonYears = `${seasonYmin}~${seasonYmax} · ${seasonYmax - seasonYmin + 1}년`;

  const 상수도계 = bill.상수도_합계 ??
    (bill.상수도_기본료 != null && bill.상수도_사용료 != null ? bill.상수도_기본료 + bill.상수도_사용료 : null);

  return (
    <>
      <div className="dt-bill-toolbar">
        <label className="dt-field">
          청구 연도
          <select value={bill.year} onChange={(e) => onYear(e.target.value)}>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}년
              </option>
            ))}
          </select>
        </label>
        <label className="dt-field">
          청구 월
          <select value={bill.month} onChange={(e) => onMonth(e.target.value)}>
            {monthsOfYear.map((m) => (
              <option key={m} value={m}>
                {m}월
              </option>
            ))}
          </select>
        </label>
        <label className="dt-field">청구 구분<select value={keyOf(bill)} onChange={(e) => setSelected(e.target.value)}>{bills.filter((b) => b.ym === bill.ym).map((b) => <option key={keyOf(b)} value={keyOf(b)}>{billLabel(b)}</option>)}</select></label>
        <span className="dt-bimonthly">청구자료가 있는 월만 표시 <InfoTooltip text="월별·격월 청구를 실제 청구 이력에 따라 표시합니다. 아래 비교 차트는 선택한 청구 구분 기준입니다." /></span>
        {bill.id && <div className="pdf-actions"><FileLink href={pdfUrl(bill.id)} preview filename={pdfFilename}>PDF 열람 ↗</FileLink><FileLink href={pdfUrl(bill.id, true)} filename={pdfFilename}>PDF 다운로드</FileLink></div>}
      </div>
      <p className="form-hint">PDF는 저장된 자료로 만든 청구내역 문서입니다. 공급기관의 원본 고지서와 구분됩니다.</p>
      {(bill.summary_only || bill.detail_available === false) && <p className="data-notice">{bill.summary_only ? "요약 수집 · 상세 미확인 — 부과금액과 총사용량을 확인한 자료입니다." : "상세 미확인 — 확인된 청구 항목만 표시합니다."} 개별 요금·검침 내역의 빈칸은 확인되지 않은 값입니다.</p>}

      {/* ── 사진1 재현 영역 ─────────────────────────────── */}
      <div className="dt-bill">
        <div className="dt-bill-top">
          <div>
            <h4 className="dt-bill-title">
              {bill.year}년 {bill.month}월 상·하수도요금, 물이용부담금
            </h4>
            <dl className="dt-bill-meta">
              <div>
                <dt>성명</dt>
                <dd>{bill.고지서성명 || bill.사용자명 || bill.성명 || station.사용자명}</dd>
              </div>
              <div>
                <dt>주소</dt>
                <dd>{bill.주소 || station.주소}</dd>
              </div>
              <div><dt>납기일</dt><dd>{fmtK(bill.납기일)}</dd></div>
            </dl>
          </div>
          <table className="dt-bill-idtable">
            <tbody>
              <tr>
                <th>고객번호</th>
                <td>{line.고객번호}</td>
              </tr>
              {noticeNumber && <tr><th>고지번호</th><td>{noticeNumber}</td></tr>}
              <tr>
                <th>전자수용가번호</th>
                <td>{bill.전자수용가번호 ?? line.전자수용가번호 ?? "—"}</td>
              </tr>
              <tr>
                <th>전자납부번호</th>
                <td>{bill.전자납부번호 ?? line.전자납부번호 ?? "—"}</td>
              </tr>
              <tr>
                <th>납부방법</th>
                <td>{bill.납부방법 || "—"}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="dt-bill-pay">
          <span>{paymentLabel}</span>
          <strong>{nz(payment)}원</strong>
        </div>

        <table className="dt-bill-grid">
          <thead>
            <tr>
              <th>총 사용금액</th>
              <th>차감금액</th>
              <th>{paymentLabel}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{nz(bill.총사용금액)}</td>
              <td>{nz(bill.차감금액)}</td>
              <td>{nz(payment)}</td>
            </tr>
          </tbody>
        </table>

        <table className="dt-bill-grid">
          <thead>
            <tr>
              <th>내역</th>
              <th>상수도요금</th>
              <th>하수도요금</th>
              <th>물이용부담금</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>기본요금</th>
              <td>{nz(bill.상수도_기본료)}</td>
              <td>{nz(bill.하수도_기본료)}</td>
              <td></td>
            </tr>
            <tr>
              <th>사용요금</th>
              <td>{nz(bill.상수도_사용료)}</td>
              <td>{nz(bill.하수도_사용료)}</td>
              <td>{nz(bill.물이용부담금)}</td>
            </tr>
            <tr className="dt-bill-sum">
              <th>계</th>
              <td>{nz(상수도계)}</td>
              <td>{nz(bill.하수도_사용료)}</td>
              <td>{nz(bill.물이용부담금)}</td>
            </tr>
          </tbody>
        </table>

        {additionalFees.length > 0 && <table className="dt-bill-grid"><thead><tr>{additionalFees.map((key) => <th key={key}>{key} (원)</th>)}</tr></thead><tbody><tr>{additionalFees.map((key) => <td key={key}>{nz(bill[key])}</td>)}</tr></tbody></table>}

        <div className="dt-bill-period">
          사용기간 {fmtK(bill.periodStart)} ~ {fmtK(bill.periodEnd)}
        </div>

        <div className="dt-bill-cols">
          <table className="dt-bill-grid">
            <thead>
              <tr>
                <th>정기검침일 {bill.정기검침일 ?? "—"}</th>
                <th>상·하수도</th>
                <th>지하수</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>당월지침</th>
                <td>{nz(bill.당월지침)}</td>
                <td>{nz(groundwater.current)}</td>
              </tr>
              <tr>
                <th>전월지침</th>
                <td>{nz(bill.전월지침)}</td>
                <td>{nz(groundwater.previous)}</td>
              </tr>
              <tr className="dt-bill-sum">
                <th>사용량</th>
                <td>{nz(usageOf(bill))}</td>
                <td>{nz(groundwater.usage)}</td>
              </tr>
            </tbody>
          </table>

          <table className="dt-bill-kv">
            <tbody>
              <tr>
                <th>공동사용량</th>
                <td>{nz(bill.공동사용량)}</td>
                <th>전납기사용량</th>
                <td>{nz(bill.전납기사용량)}</td>
              </tr>
              <tr>
                <th>총사용량</th>
                <td>{nz(bill.총사용량 ?? bill.사용량)}</td>
                <th>전년동기사용량</th>
                <td>{nz(bill.전년동기사용량)}</td>
              </tr>
              <tr>
                <th>업종</th>
                <td>{bill.업종 || bill.용도 || line.tariff || "—"}</td>
                <th>가구수</th>
                <td>{bill.가구수 ?? line.가구수 ?? "—"}</td>
              </tr>
              <tr>
                <th>계량기번호</th>
                <td>{bill.계량기번호 ?? line.계량기번호 ?? "—"}</td>
                <th>구경</th>
                <td>{bill.구경 ?? line.구경 ?? "—"}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>

      {/* ── 추세 + 전년대비 좌우 배치 ───────────────────── */}
      {groundwater.usage != null && <p className="form-hint">비교 차트는 상·하수도 사용량 기준입니다. 지하수 사용량은 위 검침 내역에서 별도로 확인할 수 있습니다.</p>}
      <div className="dt-bill-charts">
        <div className="dt-bill-trend">
          <SectionTitle>최근 1년간 사용량</SectionTitle>
          <LineChart
            series={[{ color: "#283891", values: trend.values, fill: true }]}
            xLabels={trend.labels}
            height={200}
            labelEvery={1}
            showValues
            formatValue={won}
            formatY={won}
            yUnit="톤"
            xUnit="연/월"
          />
        </div>

        <div className="dt-yoy">
          <SectionTitle
            right={
              <>
                <span className="dt-deltachip">
                  전년 대비{" "}
                  <b className={dPrev != null && dPrev > 0 ? "up" : "down"}>
                    {dPrev == null ? "–" : `${dPrev > 0 ? "+" : ""}${dPrev}%`}
                  </b>
                </span>
                <span className="dt-deltachip">
                  이전 {histVals.length}개년 평균 대비{" "}
                  <b className={dAvg != null && dAvg > 0 ? "up" : "down"}>
                    {dAvg == null ? "–" : `${dAvg > 0 ? "+" : ""}${dAvg}%`}
                  </b>
                </span>
              </>
            }
          >
            최근 5년 동월 비교
          </SectionTitle>
          <div className="dt-yoy-chart">
            <LineChart
              series={[{ color: "#b08a4f", values: yoyValues, fill: true }]}
              xLabels={yoyLabels}
              height={185}
              labelEvery={1}
              showValues
              formatValue={won}
              formatY={won}
              yUnit="톤"
              xUnit="연/월"
            />
          </div>
        </div>

        <div className="dt-yoy">
          <SectionTitle right={<span className="dt-risk-date">{seasonYears} 평균</span>}>계절별 추이</SectionTitle>
          <div className="dt-yoy-chart">
            <LineChart
              series={[{ color: "#0e7c7b", values: seasonValues, fill: true }]}
              xLabels={seasonLabels}
              height={185}
              labelEvery={1}
              showValues
              formatValue={won}
              formatY={won}
              yUnit="톤"
              xUnit="월"
            />
          </div>
        </div>
      </div>
    </>
  );
}

function fmtK(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "—";
  const [y, m, d] = iso.split("-");
  return `${y}년 ${Number(m)}월 ${Number(d)}일`;
}
