export default function SwitchField({ label, checked, ...props }) {
  return (
    <label className="switch-field">
      <input type="checkbox" checked={Boolean(checked)} {...props} />
      <span>{label}</span>
    </label>
  );
}
