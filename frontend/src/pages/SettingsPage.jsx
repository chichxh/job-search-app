import ErrorBanner from '../components/ErrorBanner.jsx';

export default function SettingsPage() {
  return (
    <section className="page-stack">
      <h1>Settings</h1>
      <ErrorBanner message="Settings form is not connected yet." />
    </section>
  );
}
