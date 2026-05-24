const NUMBER_FORMATTER = new Intl.NumberFormat('ru-RU');

export function getSafeText(value, fallback) {
  if (value == null) {
    return fallback;
  }

  const text = String(value).trim();
  return text.length > 0 ? text : fallback;
}

export function formatSalary(vacancy, options = {}) {
  const {
    emptyLabel = 'Зарплата не указана',
    отLabel = 'от',
    toLabel = 'до',
  } = options;

  const salaryFrom = vacancy?.salary_от;
  const salaryTo = vacancy?.salary_to;
  const currency = vacancy?.currency;

  if (salaryFrom == null && salaryTo == null) {
    return emptyLabel;
  }

  const отPart = salaryFrom != null ? NUMBER_FORMATTER.format(salaryFrom) : null;
  const toPart = salaryTo != null ? NUMBER_FORMATTER.format(salaryTo) : null;
  const currencyPart = currency ? ` ${currency}` : '';

  if (отPart && toPart) {
    return `${отPart} - ${toPart}${currencyPart}`;
  }

  if (отPart) {
    return `${отLabel} ${отPart}${currencyPart}`;
  }

  return `${toLabel} ${toPart}${currencyPart}`;
}

export function formatDateTime(value, locale = 'ru-RU') {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
