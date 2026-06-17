import { useMemo, useState } from "react";
import { won } from "./data";
import { InfoTooltip, SectionTitle } from "./ui";
import LineChart from "./LineChart";

// i121 인쇄화면(사진1)을 최대한 유사하게 재현하는 청구서 카드.
// 실데이터(bills.json) 연결. 검침 미수집분은 칸을 "—" 로, 차트는 gap 으로 처리.
export default function Bill({ station, line }) {
  const bills = line.bills;
  const nz = (n) => (n == null ? "—" : won(n)); // 결측 칸은 "—"
  const [ym, setYm] = useState(bills[bills.length - 1].ym);
  const bill = useMemo(() => bills.find((b) => b.ym === ym) ?? bills[bills.length - 1], [bills, ym]);

  const years = useMemo(() => [...new Set(bills.map((b) => b.year))].sort(), [bills]);
  const monthsOfYear = useMemo(
    () => bills.filter((b) => b.year === bill.year).map((b) => b.month).sort((a, b) => a - b),
    [bills, bill.year]
  );
  const onYear = (y) => {
    const inYear = bills.filter((b) => b.year === Number(y));
    setYm(inYear[inYear.length - 1].ym);
  };
  const onMonth = (m) => setYm(`${bill.year}-${String(m).padStart(2, "0")}`);

  // 최근 1년(격월 7포인트) 추세
  const idx = bills.findIndex((b) => b.ym === bill.ym);
  const window = bills.slice(Math.max(0, idx - 6), idx + 1);
  const trend = {
    values: window.map((b) => b.사용량),
    labels: window.map((b) => b.ym.slice(2).replace("-", "/")),
  };

  // 최근 5년 동월 비교
  const YOY_N = 5;
  const mm = String(bill.month).padStart(2, "0");
  const yoyYears = Array.from({ length: YOY_N }, (_, k) => bill.year - (YOY_N - 1) + k);
  const yoyLabels = yoyYears.map((y) => `${String(y).slice(2)}/${mm}`);
  const yoyValues = yoyYears.map((y) => bills.find((b) => b.year === y && b.month === bill.month)?.사용량 ?? null);
  const cur = bill.사용량;
  const prevYearVal = yoyValues[YOY_N - 2];
  const dPrev = cur != null && prevYearVal ? Math.round(((cur - prevYearVal) / prevYearVal) * 100) : null;
  const histVals = yoyValues.slice(0, YOY_N - 1).filter((v) => v != null);
  const avgHist = histVals.length ? histVals.reduce((a, b) => a + b, 0) / histVals.length : null;
  const dAvg = cur != null && avgHist ? Math.round(((cur - avgHist) / avgHist) * 100) : null;

  // 계절별 추이: 청구(납기) 월이 역마다 홀/짝으로 갈려서 실제 데이터에서 추출(하드코딩 X). 월별 전기간 평균
  const billMonths = [...new Set(bills.map((b) => b.month))].sort((a, b) => a - b);
  const seasonValues = billMonths.map((m) => {
    const vs = bills.filter((b) => b.month === m).map((b) => b.사용량).filter((v) => v != null);
    return vs.length ? Math.round(vs.reduce((a, b) => a + b, 0) / vs.length) : null;
  });
  const seasonLabels = billMonths.map((m) => String(m));
  const seasonYrs = bills.map((b) => b.year);
  const seasonYmin = Math.min(...seasonYrs);
  const seasonYmax = Math.max(...seasonYrs);
  const seasonYears = `${seasonYmin}~${seasonYmax} · ${seasonYmax - seasonYmin + 1}년`;

  const 상수도계 =
    bill.상수도_기본료 != null && bill.상수도_사용료 != null ? bill.상수도_기본료 + bill.상수도_사용료 : null;

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
        <span className="dt-bimonthly">
          격월 청구 (청구되는 월만 선택)
          <InfoTooltip text={"이 역의 상·하수도요금은 격월(2개월)로 부과됩니다.\n청구가 없는 달은 선택지에 나오지 않습니다."} />
        </span>
      </div>

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
                <dd>{station.사용자명}</dd>
              </div>
              <div>
                <dt>주소</dt>
                <dd>{station.주소}</dd>
              </div>
            </dl>
          </div>
          <table className="dt-bill-idtable">
            <tbody>
              <tr>
                <th>고객번호</th>
                <td>{line.고객번호}</td>
              </tr>
              <tr>
                <th>전자수용가번호</th>
                <td>{line.전자수용가번호}</td>
              </tr>
              <tr>
                <th>전자납부번호</th>
                <td>{line.전자납부번호}</td>
              </tr>
              <tr>
                <th>납부방법</th>
                <td>{bill.납부방법 ?? "직접납부"}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="dt-bill-pay">
          <span>납부금액</span>
          <strong>{nz(bill.납부금액)}원</strong>
        </div>

        <table className="dt-bill-grid">
          <thead>
            <tr>
              <th>총 사용금액</th>
              <th>차감금액</th>
              <th>납부금액</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{nz(bill.총사용금액 ?? bill.납부금액)}</td>
              <td>{won(bill.차감금액 ?? 0)}</td>
              <td>{nz(bill.납부금액)}</td>
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
              <td>0</td>
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
                <td>0</td>
              </tr>
              <tr>
                <th>전월지침</th>
                <td>{nz(bill.전월지침)}</td>
                <td>0</td>
              </tr>
              <tr className="dt-bill-sum">
                <th>사용량</th>
                <td>{nz(bill.사용량)}</td>
                <td>0</td>
              </tr>
            </tbody>
          </table>

          <table className="dt-bill-kv">
            <tbody>
              <tr>
                <th>공동사용량</th>
                <td>0</td>
                <th>전납기사용량</th>
                <td>{nz(bill.전납기사용량)}</td>
              </tr>
              <tr>
                <th>총사용량</th>
                <td>{nz(bill.사용량)}</td>
                <th>전년동기사용량</th>
                <td>{nz(bill.전년동기사용량)}</td>
              </tr>
              <tr>
                <th>업종</th>
                <td>{station.용도 ?? "—"}</td>
                <th>가구수</th>
                <td>{line.가구수 ?? 0}</td>
              </tr>
              <tr>
                <th>계량기번호</th>
                <td>{line.계량기번호 ?? "—"}</td>
                <th>구경</th>
                <td>{line.구경 ?? "—"}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>

      {/* ── 추세 + 전년대비 좌우 배치 ───────────────────── */}
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
                  5년 평균 대비{" "}
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
  const [y, m, d] = iso.split("-");
  return `${y}년 ${Number(m)}월 ${Number(d)}일`;
}
