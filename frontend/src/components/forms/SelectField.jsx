export default function SelectField({ label, options, placeholder = 'Не выбрано', ...props }) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <select className="form-input" {...props}>
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
