export default function ErrorBanner({ message = 'Что-то пошло не так.' }) {
  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      {message}
    </div>
  );
}
