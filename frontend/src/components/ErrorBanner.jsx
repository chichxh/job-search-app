export default function ErrorBanner({ message = 'Something went wrong.' }) {
  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      {message}
    </div>
  );
}
