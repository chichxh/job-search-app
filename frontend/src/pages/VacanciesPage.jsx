import { useEffect, useMemo, useState } from 'react';

import { getVacancies } from '../api/endpoints.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import VacancyCard from '../components/VacancyCard.jsx';
import { formatDateTime, formatSalary, getSafeText } from '../utils/formatters.js';

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
          setVacancies(Array.isArray(response) ? response : []);
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
        normalizedSearch.length === 0
        || title.includes(normalizedSearch)
        || company.includes(normalizedSearch)
        || location.includes(normalizedSearch);

      if (!matchesSearch) {
        return false;
      }

      if (!onlyOpen) {
        return true;
      }

      return vacancy.status?.toLowerCase() === 'open';
    });
  }, [normalizedSearch, onlyOpen, vacancies]);

  const emptyStateMessage = vacancies.length === 0
    ? 'Пока нет вакансий. Импортируйте вакансии, чтобы они появились здесь.'
    : 'Нет вакансий по текущим фильтрам. Попробуйте изменить поиск или отключить "Only open".';

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
                title={getSafeText(vacancy.title, 'Vacancy title not specified')}
                company={getSafeText(vacancy.company_name ?? vacancy.company, 'Company not specified')}
                location={getSafeText(vacancy.location, 'Location not specified')}
                salary={formatSalary(vacancy)}
                createdAt={formatDateTime(vacancy.created_at)}
                updatedAt={formatDateTime(vacancy.updated_at)}
                to={`/vacancies/${vacancy.id}`}
              />
            ))}
          </div>
        ) : (
          <p className="loading">{emptyStateMessage}</p>
        )
      ) : null}
    </section>
  );
}
