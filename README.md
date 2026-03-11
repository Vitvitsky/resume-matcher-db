# resume-matcher-db

**PostgreSQL сервис хранения для Resume Matcher.**

Отдельный UV-проект, отвечающий за:
- Запуск PostgreSQL 16 через Docker
- Управление схемой базы данных (Alembic-миграции)
- Версионирование и накатку изменений схемы

Движок (`resume-matcher-engine`) подключается к этой БД через `DATABASE_URL` в своём `.env`.
По умолчанию движок работает с SQLite — PostgreSQL активируется явно.

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

После этого прописать `DATABASE_URL` в `.env` движка:

```bash
# resume-matcher-engine/.env
DATABASE_URL=postgresql+psycopg2://resume_matcher:your_password@localhost:5432/resume_matcher
```

---

## Структура проекта

```
resume-matcher-db/
├── alembic/
│   ├── env.py                        ← Конфигурация Alembic (читает DATABASE_URL)
│   ├── script.py.mako                ← Шаблон файлов миграций
│   └── versions/
│       └── 001_initial_schema.py     ← Начальная схема (все 12 таблиц)
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

12 таблиц, соответствующих ORM-моделям в `resume-matcher-engine/src/database/models.py`:

| Таблица | Назначение |
|---------|-----------|
| `vacancy_cache` | Кэш проанализированных вакансий (VacancyArtifact + JSON) |
| `resume_cache` | Кэш проанализированных резюме (ResumeArtifact + JSON) |
| `match_results` | Результаты скоринга резюме×вакансия (MatchArtifact) |
| `resource_order_mapping` | Маппинг РИТМ resource_order_id → vacancy_id |
| `candidate_id_mapping` | Маппинг candidate_id → resume_id |
| `user_preferences` | Настройки пользователей (LDAP → display_name) |
| `candidates` | Мастер-таблица кандидатов (дедупликация по ФИО) |
| `candidate_resume_links` | Связь кандидат ↔ резюме |
| `candidate_scoring_links` | Связь кандидат ↔ результат скоринга |
| `interview_transcriptions` | Транскрипции интервью с кандидатами |
| `interview_feedbacks` | Обратная связь рекрутеров после интервью |
| `training_data` | Агрегированные данные для файн-тюнинга моделей |

JSONB-колонки используются для хранения артефактов (`artifact_json`) и вложенных структур (`segments_json`, `feedbacks_json` и др.).

---

## Добавление новой миграции

При изменении `resume-matcher-engine/src/database/models.py`:

```bash
# 1. Убедиться, что БД запущена и HEAD применён
uv run alembic current   # должно быть: 001 (head)

# 2. Сгенерировать миграцию (autogenerate сравнит models.py с текущей схемой)
uv run alembic revision --autogenerate -m "добавить колонку X в таблицу Y"

# 3. Проверить сгенерированный файл в alembic/versions/
# (убедиться, что upgrade/downgrade корректны)

# 4. Применить
uv run alembic upgrade head
```

`alembic/env.py` автоматически импортирует `Base.metadata` из `../resume-matcher-engine/src/database/models.py` — оба проекта должны находиться в одном монорепозитории.

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

- **[resume-matcher-engine](../resume-matcher-engine/)** — Backend, подключается к этой БД через `DATABASE_URL`
- **[resume-matcher-ui](../resume-matcher-ui/)** — UI, работает через HTTP API движка
