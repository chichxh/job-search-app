export default function DateField({ label, ...props }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <input className="form-input" type="date" {...props} />
    </label>
  );
}
