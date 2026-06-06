export default function SectionTitle({ title, right }) {
  return (
    <div className="section-title">
      <h2>
        <span />
        {title}
      </h2>
      {right ? <strong>{right}</strong> : null}
    </div>
  );
}
