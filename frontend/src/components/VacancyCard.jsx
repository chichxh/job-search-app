import { Link } from 'react-router-dom';

export default function VacancyCard({
  title,
  company,
  location,
  salary,
  createdAt,
  updatedAt,
  onClick,
  to,
}) {
  const content = (
    <>
      <h3 className="vacancy-card__title">{title}</h3>
      <p className="vacancy-card__meta">{company}</p>
      <p className="vacancy-card__meta">{location}</p>
      <p className="vacancy-card__salary">{salary}</p>
      {createdAt || updatedAt ? (
        <p className="vacancy-card__dates">
          {updatedAt ? `Обновлено: ${updatedAt}` : null}
          {updatedAt && createdAt ? ' · ' : null}
          {createdAt ? `Создано: ${createdAt}` : null}
        </p>
      ) : null}
    </>
  );

  if (to) {
    return (
      <Link className="vacancy-card vacancy-card--link" to={to}>
        {content}
      </Link>
    );
  }

  return (
    <button className="vacancy-card vacancy-card--button" type="button" onClick={onClick}>
      {content}
    </button>
  );
}
