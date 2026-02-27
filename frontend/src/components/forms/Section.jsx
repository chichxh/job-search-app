export default function Section({ title, defaultOpen = false, children }) {
  return (
    <details className="settings-details" open={defaultOpen}>
      <summary>{title}</summary>
      <div className="settings-details__content">{children}</div>
    </details>
  );
}
