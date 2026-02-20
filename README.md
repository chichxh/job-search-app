# job-search-app

## HH clusters and extra params

- To preview HH facets (clusters), call `POST /api/v1/import/hh/clusters` with the same body as `/api/v1/import/hh` (`text` is required, plus optional `area`, etc.).
- The response contains `found`, HH `clusters`, and `applied_base_params`.
- Cluster items may include `params` parsed from HH `url`; send them back as `extra_params` in `/api/v1/import/hh` to narrow import results.
- `extra_params` supports values: `string`, `number`, `boolean`, `list[string|number]`, or `null`.

## Saved searches with extra HH filters

- Saved searches now store `filters_json` (JSONB) with additional HH query params (for example, `metro`, `professional_role`).
- New API endpoints under `/api/v1/saved-searches`:
  - `POST /saved-searches`
  - `GET /saved-searches`
  - `PATCH /saved-searches/{id}`
  - `POST /saved-searches/{id}/sync`
  - `GET /saved-searches/{id}/clusters`
- Periodic Celery sync uses `filters_json` from `saved_searches` when requesting HH vacancies.
