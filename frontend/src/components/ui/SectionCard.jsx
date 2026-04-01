export default function SectionCard({ title, subtitle, actions, className = '', children }) {
  return (
    <section className={`section-card ${className}`.trim()}>
      {(title || subtitle || actions) ? (
        <header className="section-card__header">
          <div>
            {title ? <h2 className="section-card__title">{title}</h2> : null}
            {subtitle ? <p className="section-card__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="section-card__actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}
