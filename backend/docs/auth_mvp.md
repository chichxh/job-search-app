# Auth MVP (JWT + ownership foundation)

## Что реализовано

- Добавлена таблица `users` (`email` unique + indexed, `password_hash`, `is_active`, timestamps).
- В `profiles` добавлено поле `user_id` (FK -> `users.id`).
- Auth реализован через stateless JWT access token (Bearer).

## Новые endpoints

- `POST /api/v1/auth/register`
  - принимает `email`, `password`;
  - создаёт `user`;
  - автоматически создаёт пустой `profile` для этого пользователя;
  - возвращает access token.
- `POST /api/v1/auth/login`
  - принимает `email`, `password`;
  - возвращает access token.
- `GET /api/v1/auth/me`
  - требует Bearer token;
  - возвращает текущего пользователя и `profile_id`, принадлежащий этому пользователю.

## Ownership enforcement (profile-scoped API)

- Profile-scoped роуты переведены на ownership-aware поведение и теперь требуют `Bearer` token.
- Доступ к профилю и связанным сущностям (profile data, applications, recommendations/tailoring, docgen) разрешён только владельцу профиля.
- Введена единая deny policy: при попытке обратиться к чужому `profile_id` или чужому profile-bound ресурсу API возвращает `404 Resource not found` (чтобы не раскрывать наличие чужих данных).
- Для реализации добавлены helpers:
  - `get_owned_profile(...)`;
  - `get_owned_profile_resource(...)`.

## Миграция и demo bootstrap

Alembic migration `2b7d4e1a9c3f_add_users_and_profile_ownership`:

1. создаёт `users` и unique index по `email`;
2. добавляет `profiles.user_id`;
3. создаёт demo пользователя `demo@example.local`;
4. привязывает существующие профили к demo пользователю;
5. делает `profiles.user_id` обязательным (`NOT NULL`) и добавляет FK.

Это сохраняет совместимость для существующих demo данных и убирает схему без ownership.
