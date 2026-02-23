export const JOBSEARCH_SETTINGS_KEY = 'jobsearch_settings';

export const DEFAULT_JOBSEARCH_SETTINGS = {
  recommendationsLimit: 50,
  hideReject: true,
  autoRecomputeAfterProfileSave: false,
  scoringMode: 'Balanced',
};

const ALLOWED_SCORING_MODES = new Set([
  'Balanced',
  'Conservative',
  'Startup',
  'Enterprise',
]);

function clampRecommendationsLimit(value) {
  const parsed = Number.parseInt(value, 10);

  if (Number.isNaN(parsed)) {
    return DEFAULT_JOBSEARCH_SETTINGS.recommendationsLimit;
  }

  return Math.max(10, Math.min(200, parsed));
}

export function normalizeSettings(rawSettings) {
  const settings = rawSettings && typeof rawSettings === 'object' ? rawSettings : {};
  const scoringMode = ALLOWED_SCORING_MODES.has(settings.scoringMode)
    ? settings.scoringMode
    : DEFAULT_JOBSEARCH_SETTINGS.scoringMode;

  return {
    recommendationsLimit: clampRecommendationsLimit(settings.recommendationsLimit),
    hideReject:
      typeof settings.hideReject === 'boolean'
        ? settings.hideReject
        : DEFAULT_JOBSEARCH_SETTINGS.hideReject,
    autoRecomputeAfterProfileSave:
      typeof settings.autoRecomputeAfterProfileSave === 'boolean'
        ? settings.autoRecomputeAfterProfileSave
        : DEFAULT_JOBSEARCH_SETTINGS.autoRecomputeAfterProfileSave,
    scoringMode,
  };
}

export function loadJobSearchSettings() {
  try {
    const raw = window.localStorage.getItem(JOBSEARCH_SETTINGS_KEY);
    if (!raw) {
      return DEFAULT_JOBSEARCH_SETTINGS;
    }

    const parsed = JSON.parse(raw);
    return normalizeSettings(parsed);
  } catch {
    return DEFAULT_JOBSEARCH_SETTINGS;
  }
}

export function saveJobSearchSettings(settings) {
  const normalized = normalizeSettings(settings);
  window.localStorage.setItem(JOBSEARCH_SETTINGS_KEY, JSON.stringify(normalized));
  return normalized;
}
