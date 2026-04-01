# Resume file import (MVP) — reproducible flow

Этот документ фиксирует **канонический flow** импорта резюме в профиль кандидата для команды, demo и ручной верификации.

## Canonical sample files (fixtures)

Рекомендуемые файлы для локальной проверки и regression smoke:

- `backend/tests/fixtures/resume/sample_resume.txt`
- `backend/tests/fixtures/resume/sample_resume.pdf` (text-based PDF)
- `backend/tests/fixtures/resume/low_signal_resume.txt` (проверка low-signal/too short)
- `backend/tests/fixtures/resume/no_text_resume.pdf` (edge case: PDF без извлекаемого текста)

## Supported vs unsupported formats

### Supported now

- `.txt`
- `.md`
- `.docx`
- `.pdf` (**только text-based PDF**)
- `.rtf`

### Not supported (MVP limitation)

- scanned PDFs (image-only) — extraction вернёт ошибку `no extractable text`
- image files (`.png`, `.jpg`, `.jpeg`, etc.)
- `.doc` (legacy binary Word format)
- произвольные бинарные файлы

## User flow (Settings → Resume import)

1. **Upload**: пользователь выбирает файл (`txt/docx/pdf/rtf/md`) в Settings.
2. **Extract**: backend извлекает raw text из файла.
3. **Parse preview**: backend парсит extracted text в draft profile preview (name/title/skills/experience/etc.).
4. **Apply**: пользователь применяет draft к профилю (main fields + выбранные sections).

## Verification checklist (manual)

1. Login под тестовым пользователем.
2. Открыть страницу **Settings**.
3. Upload по очереди:
   - `sample_resume.txt`
   - `sample_resume.pdf`
4. Для каждого файла убедиться, что `extracted text` не пустой (`text length > 0`).
5. Проверить `parse preview`:
   - есть `full_name/title`
   - `experiences/skills/languages/links` имеют ожидаемое количество.
6. Нажать **Apply import**.
7. Проверить, что профиль обновился:
   - main fields (`full_name`, `title`, etc.)
   - experiences
   - skills
8. Negative checks:
   - `low_signal_resume.txt` должен приводить к ошибке low-signal/too-short;
   - `no_text_resume.pdf` должен приводить к ошибке no-extractable-text.

## Operational / logging notes

- **Resume raw text не должен попадать в operational logs**.
- Ошибки extraction/parsing логировать в формате **summary-only** (без `extracted_text` и без содержимого файла).
- Путь сохранения upload-файлов (если включён локальный debug persistence) должен быть безопасен для local/dev:
  - внутри локальной рабочей директории проекта,
  - без записи в системные директории,
  - без публикации содержимого в stdout/stderr.

## Demo recommendation

Для demo сначала пройти happy-path на `sample_resume.txt`, затем показать форматную устойчивость на `sample_resume.pdf` и (опционально) на локально подготовленном `.docx`, а в конце — ограничение MVP (`no_text_resume.pdf` / scanned PDF).
