import { useLayoutEffect, useRef, useState } from "react";

// 의존성 없는 SVG 라인차트.
// 컨테이너 실제 너비를 측정해 viewBox=픽셀 1:1 로 그림 → 폭이 달라도 글씨 크기·여백이 일정.
// series: [{ color, values: number[], fill?: bool }] / xLabels: string[]
// labelEvery: x라벨 간격 / showValues: 각 점 위 값 표기 / yUnit·xUnit: 축 단위
export default function LineChart({
  series,
  xLabels = [],
  height = 170,
  formatY = (v) => v,
  formatValue,
  showValues = false,
  labelEvery,
  yUnit = "",
  xUnit = "",
  bars = false,
}) {
  const wrapRef = useRef(null);
  const [W, setW] = useState(640);
  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => setW(Math.max(260, el.clientWidth));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const H = height;
  const padL = 92; // 그래프(첫 점·그리드) 시작을 오른쪽으로 → y축 숫자와 간격 확보
  const padR = 28;
  const yLabelX = 60; // y축 숫자 끝 위치(왼쪽 고정). padL 과의 차이가 곧 여백
  const padT = showValues ? 28 : 16;
  const padB = 40;

  const all = series.flatMap((s) => s.values).filter((v) => Number.isFinite(v));
  const rawMin = all.length ? Math.min(...all) : 0;
  const rawMax = all.length ? Math.max(...all) : 1;
  const span = rawMax - rawMin || 1;
  const lo = rawMin - span * 0.14;
  const hi = rawMax + span * (showValues ? 0.2 : 0.14);
  const n = series[0].values.length;

  const slot = (W - padL - padR) / n;
  const X = bars
    ? (i) => padL + slot * (i + 0.5)
    : (i) => padL + (W - padL - padR) * (n <= 1 ? 0.5 : i / (n - 1));
  const Y = (v) => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));

  // null/결측은 선을 끊어서(gap) 그림 → 검침 미수집 구간 표현
  const line = (vals) => {
    let d = "";
    let pen = false;
    vals.forEach((v, i) => {
      if (!Number.isFinite(v)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)} `;
      pen = true;
    });
    return d.trim();
  };
  const areaPath = (vals) =>
    vals.some((v) => !Number.isFinite(v))
      ? "" // 결측이 있으면 면적 채움 생략(끊긴 구간 음영 방지)
      : `${line(vals)} L${X(n - 1).toFixed(1)},${Y(lo).toFixed(1)} L${X(0).toFixed(1)},${Y(lo).toFixed(1)} Z`;

  const yTicks = [hi, (lo + hi) / 2, lo];
  const step = labelEvery || Math.max(1, Math.ceil(n / 6));
  const fv = formatValue || formatY;

  return (
    <div ref={wrapRef} className="dt-chart-wrap">
      <svg className="dt-chart" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img">
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={Y(t)} y2={Y(t)} className="dt-chart-grid" />
            <text x={yLabelX} y={Y(t) + 4} textAnchor="end" className="dt-chart-axis">
              {formatY(Math.round(t))}
            </text>
          </g>
        ))}
        {xLabels.map((lab, i) =>
          i % step === 0 || i === n - 1 ? (
            <text key={i} x={X(i)} y={H - 24} textAnchor="middle" className="dt-chart-axis">
              {lab}
            </text>
          ) : null
        )}
        {yUnit ? (
          <text x={yLabelX} y={15} textAnchor="end" className="dt-chart-unit">
            {yUnit}
          </text>
        ) : null}
        {xUnit ? (
          <text x={W - 4} y={H - 6} textAnchor="end" className="dt-chart-unit">
            {xUnit}
          </text>
        ) : null}
        {!bars &&
          series.map((s, si) => (s.fill ? <path key={`a${si}`} d={areaPath(s.values)} fill={s.color} opacity="0.08" /> : null))}
        {!bars &&
          series.map((s, si) => (
            <path key={`l${si}`} d={line(s.values)} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinejoin="round" />
          ))}
        {bars &&
          series[0].values.map((v, i) => (
            <rect
              key={`bar${i}`}
              x={X(i) - slot * 0.29}
              y={Y(v)}
              width={slot * 0.58}
              height={Math.max(0, Y(lo) - Y(v))}
              rx="4"
              fill={series[0].color}
              opacity="0.9"
            />
          ))}
        {series.map((s, si) =>
          s.values.map((v, i) =>
            showValues && Number.isFinite(v) ? (
              <text key={`v${si}-${i}`} x={X(i)} y={Y(v) - 10} textAnchor="middle" className="dt-chart-value">
                {fv(v)}
              </text>
            ) : null
          )
        )}
        {!bars &&
          series.map((s, si) =>
            s.values.map((v, i) =>
              Number.isFinite(v) ? (
                <circle
                  key={`d${si}-${i}`}
                  cx={X(i)}
                  cy={Y(v)}
                  r={i === n - 1 ? 4 : 2.6}
                  fill={s.color}
                  stroke="#fff"
                  strokeWidth={i === n - 1 ? 1.6 : 1.1}
                />
              ) : null
            )
          )}
      </svg>
    </div>
  );
}
