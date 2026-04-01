const LABELS = {
  strong: 'Strong fit',
  ok: 'Potential fit',
  weak: 'Weak fit',
  reject: 'Reject',
};

export default function VerdictBadge({ verdict }) {
  const normalized = String(verdict || 'unknown').toLowerCase();

  return (
    <span className={`verdict-badge verdict-badge--${normalized}`}>
      {LABELS[normalized] ?? normalized}
    </span>
  );
}
