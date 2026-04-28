# resume-matcher-db

**PostgreSQL сервис хранения для home-стенда resume-matcher.**

Отдельный UV-проект, отвечающий за:
- Запуск PostgreSQL 16 через Docker
- Управление схемой базы данных (Alembic-миграции)
- Версионирование и накатку изменений схемы

К этой БД подключается **`resume-matcher-bff`** через `DATABASE_URL` (asyncpg).
**`resume-matcher-engine` после эпика SQLite-removal — stateless** и в БД не пишет.

---

## Быстрый старт

```bash
# 1. Установить зависимости
uv sync

# 2. Настроить переменные окружения
cp .env.example .env
# Обязательно задать POSTGRES_PASSWORD в .env

# 3. Поднять PostgreSQL
docker-compose up -d

# 4. Применить миграции
uv run alembic upgrade head
```

После этого прописать `DATABASE_URL` в `.env` BFF:

```bash
# resume-matcher-bff/.env
DATABASE_URL=postgresql+asyncpg://resume_matcher:your_password@localhost:5432/resume_matcher
```

Alembic читает sync-URL (`postgresql+psycopg2://...`) из той же `.env` через `alembic/env.py`.

---

## Структура проекта

```
resume-matcher-db/
├── alembic/
│   ├── env.py                              ← Конфигурация Alembic (читает DATABASE_URL)
│   ├── script.py.mako                      ← Шаблон файлов миграций
│   ├── models.py                           ← ORM Base (источник для autogenerate)
│   └── versions/
│       ├── 001_initial_schema.py           ← Начальная схема (12 таблиц)
│       ├── 002_add_denormalized_columns.py ← Денорм. поля в vacancy_cache (role_title/job_family/...)
│       ├── 003_home_schema.py              ← Home-дельта: drop 2 РИТМ-mapping, add 3 home-таблицы
│       ├── 004_tz_aware_datetimes.py       ← TIMESTAMP → TIMESTAMPTZ для всех 17 колонок
│       └── 005_overall_score_float.py      ← overall_score Integer → Float (precision)
├── alembic.ini                       ← Настройки Alembic
├── docker-compose.yml                ← PostgreSQL 16 с volume и healthcheck
├── pyproject.toml                    ← UV-зависимости (alembic, psycopg2-binary)
└── .env.example                      ← Шаблон переменных окружения
```

---

## Переменные окружения

Скопируйте `.env.example` в `.env` и задайте значения:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `POSTGRES_DB` | Имя базы данных | `resume_matcher` |
| `POSTGRES_USER` | Пользователь | `resume_matcher` |
| `POSTGRES_PASSWORD` | Пароль **(обязательно задать)** | — |
| `POSTGRES_PORT` | Порт на хосте | `5432` |
| `DATABASE_URL` | Полный URL подключения (для Alembic) | — |

`DATABASE_URL` используется и в `alembic/env.py`, и в `resume-matcher-engine/.env`.

---

## Команды Alembic

```bash
# Применить все миграции (до последней версии)
uv run alembic upgrade head

# Откатить все миграции
uv run alembic downgrade base

# Показать текущую версию схемы
uv run alembic current

# Показать историю миграций
uv run alembic history

# Создать новую миграцию (autogenerate — сравнивает models.py с БД)
uv run alembic revision --autogenerate -m "описание изменений"

# Применить одну миграцию вперёд / назад
uv run alembic upgrade +1
uv run alembic downgrade -1
```

> `DATABASE_URL` должен быть задан в `.env` или передан явно:
> ```bash
> DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/resume_matcher uv run alembic current
> ```

---

## Схема базы данных

13 таблиц после revisions 001-005. Источник истины для ORM — **`resume-matcher-bff/src/db/models.py`** (engine после SQLite-removal не имеет `src/database/`). `alembic/models.py` содержит копию `Base` для `--autogenerate`.

| Таблица | Назначение | Появилась в |
|---------|-----------|-------------|
| `vacancy_cache` | Артефакты проанализированных вакансий + денорм. поля (role_title, job_family, domain, role_level, author_ldap) | 001 + 002 |
| `resume_cache` | Артефакты проанализированных резюме | 001 |
| `match_results` | Результаты скоринга резюме×вакансия (`overall_score: Float`) | 001 |
| `user_preferences` | Настройки пользователей (LDAP → display_name) | 001 |
| `candidates` | Мастер-таблица кандидатов (дедупликация по нормализованному ФИО, NFKD+casefold) | 001 |
| `candidate_resume_links` | Связь кандидат ↔ резюме | 001 |
| `candidate_scoring_links` | Связь кандидат ↔ результат скоринга (`overall_score: Float`) | 001 |
| `interview_transcriptions` | Транскрипции интервью с кандидатами | 001 |
| `interview_feedbacks` | Обратная связь рекрутеров после интервью | 001 |
| `training_data` | Агрегированные данные для файн-тюнинга моделей | 001 |
| `batches` | Батч-задачи скоринга (для `POST /scoring/batch` в BFF) | 003 |
| `llm_debug_artifacts` | Промпты + сырые ответы LLM (debug-режим) | 003 |
| `upload_files` | Метаданные загруженных файлов (kind, sha256, stored_path, ...) | 003 |

В revision 003 удалены: `resource_order_mapping`, `candidate_id_mapping` (РИТМ-специфика, дома не нужны).

JSONB-колонки хранят артефакты (`artifact_json`, `segments_json`, `feedbacks_json` и др.). Все timestamp-колонки — `TIMESTAMPTZ` (revision 004).

---

## Добавление новой миграции

При изменении схемы (источник — `resume-matcher-bff/src/db/models.py`):

```bash
# 1. Синхронизировать локальный alembic/models.py с BFF — ручной copy/diff
#    (общего пакета пока нет, контролируется ревью)

# 2. Убедиться, что БД запущена и HEAD применён
uv run alembic current   # должно быть: 005 (head)

# 3. Сгенерировать миграцию (autogenerate сравнит models.py с текущей схемой)
uv run alembic revision --autogenerate -m "добавить колонку X в таблицу Y"

# 4. Проверить сгенерированный файл в alembic/versions/
# (upgrade/downgrade, корректность ON DELETE/UPDATE, индексы)

# 5. Применить
uv run alembic upgrade head
```

`alembic/env.py` импортирует `Base.metadata` из локального `alembic/models.py`. Это **копия** ORM из BFF, синхронизируется руками — иначе autogenerate генерирует неправильный diff.

---

## Docker

```bash
# Запустить PostgreSQL
docker-compose up -d

# Остановить (данные сохраняются в volume)
docker-compose down

# Остановить и удалить данные
docker-compose down -v

# Логи
docker logs -f resume-matcher-postgres

# Подключиться к БД
docker exec -it resume-matcher-postgres psql -U resume_matcher -d resume_matcher
```

Volume `resume-matcher-postgres-data` хранит данные между перезапусками контейнера.

---

## Full-stack запуск

Для запуска всего стека (PostgreSQL + Engine + UI) использует `docker-compose.yml` в **корне монорепозитория**:

```bash
# Из корня resume-matcher/
docker-compose up -d
```

---

## Связанные проекты

- **[resume-matcher-bff](../resume-matcher-bff/)** — единственный owner persistance, подключается к этой БД через asyncpg
- **[resume-matcher-engine](../resume-matcher-engine/)** — stateless compute, к БД не ходит
- **[resume-matcher-ui](../resume-matcher-ui/)** — React SPA, ходит в BFF через REST
