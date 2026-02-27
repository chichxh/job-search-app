export default function TextField({ label, placeholder, ...props }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <input className="form-input" placeholder={placeholder ?? 'Введите значение'} {...props} />
    </label>
  );
}
