import VacancyCard from '../components/VacancyCard.jsx';

const vacancies = [
  {
    id: 1,
    title: 'Frontend Developer',
    company: 'Acme Inc.',
    location: 'Remote',
    salary: '$3,000 - $4,500',
  },
  {
    id: 2,
    title: 'React Engineer',
    company: 'Bright Labs',
    location: 'Berlin',
    salary: '$4,200 - $5,500',
  },
  {
    id: 3,
    title: 'UI Developer',
    company: 'Northwind',
    location: 'Warsaw',
    salary: '$3,700 - $4,900',
  },
];

export default function VacanciesPage() {
  return (
    <section className="page-stack">
      <h1>Vacancies</h1>
      <div className="vacancy-grid">
        {vacancies.map((vacancy) => (
          <VacancyCard
            key={vacancy.id}
            title={vacancy.title}
            company={vacancy.company}
            location={vacancy.location}
            salary={vacancy.salary}
            to={`/vacancies/${vacancy.id}`}
          />
        ))}
      </div>
    </section>
  );
}
