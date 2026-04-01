export default function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <header className="product-page-header">
      <div>
        {eyebrow ? <p className="product-page-header__eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {subtitle ? <p className="product-page-header__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="product-page-header__actions">{actions}</div> : null}
    </header>
  );
}
