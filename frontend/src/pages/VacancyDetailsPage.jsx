import { useParams } from 'react-router-dom';

export default function VacancyDetailsPage() {
  const { vacancyId } = useParams();

  return (
    <section className="page-stack">
      <h1>Vacancy details</h1>
      <p>Selected vacancy id: {vacancyId}</p>
    </section>
  );
}
