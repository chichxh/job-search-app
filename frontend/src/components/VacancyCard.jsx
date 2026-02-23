import { Link } from 'react-router-dom';

export default function VacancyCard({ title, company, location, salary, onClick, to }) {
  const content = (
    <>
      <h3 className="vacancy-card__title">{title}</h3>
      <p className="vacancy-card__meta">{company}</p>
      <p className="vacancy-card__meta">{location}</p>
      <p className="vacancy-card__salary">{salary}</p>
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
