const LABELS = {
  strong: 'Сильное соответствие',
  ok: 'Среднее соответствие',
  weak: 'Слабое соответствие',
  reject: 'Отклонено',
};

export default function VerdictBadge({ verdict }) {
  const normalized = String(verdict || 'неизвестно').toLowerCase();

  return (
    <span className={`verdict-badge verdict-badge--${normalized}`}>
      {LABELS[normalized] ?? normalized}
    </span>
  );
}
