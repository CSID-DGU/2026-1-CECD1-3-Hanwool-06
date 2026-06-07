// 디테일 화면 공통 UI 조각.

export function Card({ title, right, children, className = "", pad = true }) {
  return (
    <section className={`dt-card ${className}`}>
      {title ? (
        <header className="dt-card-head">
          <SectionTitle right={right}>{title}</SectionTitle>
        </header>
      ) : null}
      <div className={pad ? "dt-card-body" : ""}>{children}</div>
    </section>
  );
}

export function SectionTitle({ children, right }) {
  return (
    <div className="dt-sectitle">
      <h3>
        <span className="dt-bullet" />
        {children}
      </h3>
      {right ? <div className="dt-sectitle-right">{right}</div> : null}
    </div>
  );
}

const RISK_TONE = {
  정상: "ok",
  주의: "warn",
  경고: "alert",
};

export function RiskBadge({ level, size = "md" }) {
  if (!level) return <span className="dt-badge dt-badge--na">위험도 N/A</span>;
  return <span className={`dt-badge dt-badge--${RISK_TONE[level]} dt-badge--${size}`}>{level}</span>;
}

// 위험도 게이지 (아래가 트인 270° 미터. 가운데 텍스트, 채움 = fillPct 0~1, 색 = 심각도)
export function RiskGauge({ text, fillPct = 0, level, label = "" }) {
  const tone = level ? RISK_TONE[level] : "na";
  const r = 42;
  const c = 2 * Math.PI * r;
  const ARC = 0.75; // 270°
  const pct = Math.max(0, Math.min(1, fillPct));
  return (
    <div className={`dt-gauge dt-gauge--${tone}`}>
      {/* rotate 135° → 하단에 90° 간격을 두고 좌하단부터 시계방향으로 채움 */}
      <svg viewBox="0 0 110 110">
        <g transform="rotate(135 55 55)">
          <circle
            cx="55"
            cy="55"
            r={r}
            className="dt-gauge-track"
            strokeDasharray={`${(c * ARC).toFixed(1)} ${c.toFixed(1)}`}
            strokeLinecap="round"
          />
          <circle
            cx="55"
            cy="55"
            r={r}
            className="dt-gauge-arc"
            strokeDasharray={`${(c * ARC * pct).toFixed(1)} ${c.toFixed(1)}`}
            strokeLinecap="round"
          />
        </g>
      </svg>
      <div className="dt-gauge-num">
        <strong>{text}</strong>
        {label ? <small>{label}</small> : null}
      </div>
    </div>
  );
}

export function InfoTooltip({ text }) {
  return (
    <span className="dt-tip" tabIndex={0}>
      <span className="dt-tip-icon" aria-hidden>
        ℹ
      </span>
      <span className="dt-tip-bubble">{text}</span>
    </span>
  );
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div className={`dt-stat ${tone ? `dt-stat--${tone}` : ""}`}>
      <span className="dt-stat-label">{label}</span>
      <span className="dt-stat-value">{value}</span>
      {sub ? <span className="dt-stat-sub">{sub}</span> : null}
    </div>
  );
}

export function LineBadge({ line }) {
  return <span className={`dt-line dt-line--${line}`}>{line}호선</span>;
}

// 데이터 아직 없음 표시 (placeholder + TODO)
export function Pending({ children = "데이터 예정" }) {
  return <span className="dt-pending">{children}</span>;
}

export function EmptyNote({ children }) {
  return <div className="dt-empty">{children}</div>;
}
