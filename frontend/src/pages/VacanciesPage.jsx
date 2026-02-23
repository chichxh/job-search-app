import { useEffect, useMemo, useState } from 'react';

import { getVacancies } from '../api/endpoints.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import VacancyCard from '../components/VacancyCard.jsx';

function formatSalary(vacancy) {
  const { salary_from: salaryFrom, salary_to: salaryTo, currency } = vacancy;

  if (salaryFrom == null && salaryTo == null) {
    return 'Salary not specified';
  }

  const formatter = new Intl.NumberFormat('en-US');
  const fromPart = salaryFrom != null ? formatter.format(salaryFrom) : null;
  const toPart = salaryTo != null ? formatter.format(salaryTo) : null;
  const currencyPart = currency ?? '';

  if (fromPart && toPart) {
    return `${fromPart} - ${toPart} ${currencyPart}`.trim();
  }

  if (fromPart) {
    return `from ${fromPart} ${currencyPart}`.trim();
  }

  return `up to ${toPart} ${currencyPart}`.trim();
}

export default function VacanciesPage() {
  const [vacancies, setVacancies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [onlyOpen, setOnlyOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadVacancies() {
      setLoading(true);
      setError('');

      try {
        const response = await getVacancies();
        if (isMounted) {
          setVacancies(response);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || 'Failed to load vacancies.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadVacancies();

    return () => {
      isMounted = false;
    };
  }, []);

  const normalizedSearch = search.trim().toLowerCase();

  const filteredVacancies = useMemo(() => {
    return vacancies.filter((vacancy) => {
      const title = vacancy.title?.toLowerCase() ?? '';
      const company = vacancy.company_name?.toLowerCase() ?? vacancy.company?.toLowerCase() ?? '';
      const location = vacancy.location?.toLowerCase() ?? '';
      const matchesSearch =
        normalizedSearch.length === 0 ||
        title.includes(normalizedSearch) ||
        company.includes(normalizedSearch) ||
        location.includes(normalizedSearch);

      if (!matchesSearch) {
        return false;
      }

      if (!onlyOpen) {
        return true;
      }

      return vacancy.status?.toLowerCase() === 'open';
    });
  }, [normalizedSearch, onlyOpen, vacancies]);

  return (
    <section className="page-stack">
      <h1>Vacancies</h1>

      <div className="vacancy-filters" aria-label="Vacancy filters">
        <input
          className="vacancy-filters__search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title, company or location"
          aria-label="Search vacancies"
        />
        <label className="vacancy-filters__toggle">
          <input
            type="checkbox"
            checked={onlyOpen}
            onChange={(event) => setOnlyOpen(event.target.checked)}
          />
          <span>Only open</span>
        </label>
      </div>

      {loading ? <Loading message="Loading vacancies..." /> : null}
      {!loading && error ? <ErrorBanner message={error} /> : null}

      {!loading && !error ? (
        filteredVacancies.length > 0 ? (
          <div className="vacancy-grid">
            {filteredVacancies.map((vacancy) => (
              <VacancyCard
                key={vacancy.id}
                title={vacancy.title}
                company={vacancy.company_name ?? vacancy.company ?? 'Company not specified'}
                location={vacancy.location ?? 'Location not specified'}
                salary={formatSalary(vacancy)}
                to={`/vacancies/${vacancy.id}`}
              />
            ))}
          </div>
        ) : (
          <p className="loading">No vacancies found for selected filters.</p>
        )
      ) : null}
    </section>
  );
}
