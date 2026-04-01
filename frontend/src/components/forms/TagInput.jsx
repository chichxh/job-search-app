import { useMemo } from 'react';

export default function TagInput({ label, value = [], onChange, placeholder = 'тег1, тег2' }) {
  const text = useMemo(() => value.join(', '), [value]);

  function handleChange(event) {
    const parsed = event.target.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    onChange(parsed);
  }

  return (
    <label className="form-field">
      <span>{label}</span>
      <input className="form-input" value={text} onChange={handleChange} placeholder={placeholder} />
    </label>
  );
}
