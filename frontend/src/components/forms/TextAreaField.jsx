export default function TextAreaField({ label, rows = 4, placeholder, ...props }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <textarea
        className="form-input form-input--textarea"
        rows={rows}
        placeholder={placeholder ?? 'Введите значение'}
        {...props}
      />
    </label>
  );
}
