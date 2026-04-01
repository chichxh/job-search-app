export default function MetricTile({ label, value, tone = 'neutral', hint }) {
  return (
    <article className={`metric-tile metric-tile--${tone}`}>
      <p className="metric-tile__label">{label}</p>
      <p className="metric-tile__value">{value}</p>
      {hint ? <p className="metric-tile__hint">{hint}</p> : null}
    </article>
  );
}
