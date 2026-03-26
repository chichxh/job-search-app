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

## Ownership foundation

- Для проверок добавлены dependencies:
  - `get_current_user` — валидация Bearer JWT + блокировка неактивных пользователей;
  - `get_current_profile` — безопасное получение профиля текущего пользователя.
- Полный ownership-refactor всех routers **не входит** в этот PR; dependencies и схема уже готовы для поэтапного внедрения.

## Миграция и demo bootstrap

Alembic migration `2b7d4e1a9c3f_add_users_and_profile_ownership`:

1. создаёт `users` и unique index по `email`;
2. добавляет `profiles.user_id`;
3. создаёт demo пользователя `demo@example.local`;
4. привязывает существующие профили к demo пользователю;
5. делает `profiles.user_id` обязательным (`NOT NULL`) и добавляет FK.

Это сохраняет совместимость для существующих demo данных и убирает схему без ownership.
