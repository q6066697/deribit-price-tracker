# Deribit Price Tracker

Сервис раз в минуту забирает с криптобиржи [Deribit](https://docs.deribit.com/) индексные цены
`btc_usd` и `eth_usd`, сохраняет их в PostgreSQL и отдаёт через REST API на FastAPI.

**Стек:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, PostgreSQL 16,
Celery 5 + Redis, aiohttp, pytest, Docker Compose.

---

## Содержание

- [Как это работает](#как-это-работает)
- [Структура проекта](#структура-проекта)
- [API](#api)
- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [Локальный запуск без Docker](#локальный-запуск-без-docker)
- [Тесты и линтер](#тесты-и-линтер)
- [Конфигурация](#конфигурация)
- [Design decisions](#design-decisions)
- [Что можно улучшить](#что-можно-улучшить)

---

## Как это работает

```
 Celery beat ──(каждые 60 с)──► Redis ──► Celery worker
                                              │
                                              ▼
                                   PriceCollector (service)
                                     │                │
                     DeribitClient (aiohttp)    PriceRepository (SQLAlchemy)
                                     │                │
                               Deribit API        PostgreSQL
                                                      ▲
                                                      │
 HTTP-клиент ──► FastAPI routes ──► PriceQueryService ──► PriceRepository
```

1. **Celery beat** раз в `PRICE_FETCH_INTERVAL_SECONDS` (по умолчанию 60) ставит задачу в очередь Redis.
2. **Celery worker** выполняет задачу: `DeribitClient` параллельно запрашивает
   `public/get_index_price` для каждого тикера, `PriceCollector` присваивает общий UNIX timestamp
   и через `PriceRepository` сохраняет записи в одной транзакции.
3. **FastAPI** читает сохранённые данные через `PriceQueryService` → `PriceRepository`.

## Структура проекта

```
app/
├── core/config.py            # Settings: настройки из переменных окружения / .env
├── domain/                   # Предметная область, не зависит от БД и HTTP
│   ├── tickers.py            #   Ticker (Enum): btc_usd, eth_usd
│   └── prices.py             #   PriceSnapshot: одно наблюдение цены
├── db/
│   ├── models.py             # ORM-модель Price (таблица prices)
│   └── session.py            # Фабрики engine и сессий
├── clients/deribit.py        # DeribitClient: HTTP-клиент биржи на aiohttp
├── repositories/prices.py    # PriceRepository: только работа с БД
├── services/
│   ├── price_collector.py    # PriceCollector: сбор и сохранение цен
│   └── price_query.py        # PriceQueryService: логика чтения для API
├── api/
│   ├── routes/prices.py      # Эндпоинты /api/v1/prices
│   ├── dependencies.py       # Dependency Injection (сессия → репозиторий → сервис)
│   └── schemas.py            # Pydantic-схемы ответов
├── worker/
│   ├── celery_app.py         # Фабрика Celery-приложения + расписание beat
│   ├── tasks.py              # Задача сбора цен
│   └── main.py               # Точка входа для Celery CLI
└── main.py                   # create_app(): фабрика FastAPI-приложения
alembic/                      # Миграции БД
tests/                        # Unit-тесты (pytest)
```

## API

Все методы — `GET`, у каждого обязательный query-параметр `ticker` (`btc_usd` или `eth_usd`).
Интерактивная документация (Swagger UI): **http://localhost:8000/docs**

| Метод | Описание | Параметры |
|---|---|---|
| `GET /api/v1/prices` | Все сохранённые цены по валюте (по возрастанию времени) | `ticker` |
| `GET /api/v1/prices/latest` | Последняя цена валюты | `ticker` |
| `GET /api/v1/prices/by-date` | Цены за период (границы включительно) | `ticker`, `date_from`*, `date_to`* |
| `GET /health` | Проверка, что сервис жив | — |

\* `date_from`, `date_to` — необязательные, UNIX timestamp в секундах (UTC).

**Примеры:**

```bash
curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
```
```json
{"ticker": "btc_usd", "price": "67047.58000000", "timestamp": 1760450400}
```

```bash
curl "http://localhost:8000/api/v1/prices/by-date?ticker=eth_usd&date_from=1760450000&date_to=1760460000"
```

**Коды ответов:**

| Код | Когда |
|---|---|
| `200` | Успех. Для списков — массив (может быть пустым) |
| `404` | `/latest`: по тикеру ещё нет ни одной цены |
| `400` | `/by-date`: `date_from` больше `date_to` |
| `422` | Нет `ticker`, неизвестный тикер или некорректный timestamp |

## Быстрый старт (Docker)

Требуется Docker с Compose v2.

```bash
git clone <url-репозитория>
cd deribit-price-tracker
cp .env.example .env
docker compose up -d --build
```

Поднимется 5 контейнеров: `db` (PostgreSQL), `redis`, `api`, `worker`, `beat`.
Миграции применяются автоматически при старте `api`.

Проверка:

```bash
docker compose ps                         # все сервисы в статусе running / healthy
docker compose logs -f worker             # каждую минуту: "Task ... succeeded ...: 2"
curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
```

Первая цена появится примерно через минуту после старта. Остановка: `docker compose down`
(с удалением данных БД: `docker compose down -v`).

## Локальный запуск без Docker

Нужны Python 3.12+, запущенные PostgreSQL и Redis.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # затем поменять POSTGRES_HOST=localhost и REDIS_URL=redis://localhost:6379/0
alembic upgrade head

# в трёх разных терминалах:
uvicorn app.main:create_app --factory --reload
celery -A app.worker.main worker --loglevel=info
celery -A app.worker.main beat --loglevel=info
```

## Тесты и линтер

```bash
pip install -r requirements-dev.txt
pytest -v
ruff check . && ruff format --check .
```

Тесты не требуют запущенных PostgreSQL, Redis или доступа к Deribit:

| Файл | Что проверяет | Как изолирован |
|---|---|---|
| `test_deribit_client.py` | Парсинг цены, параметры запроса, ошибки API/сети/формата | Локальный aiohttp-сервер вместо Deribit |
| `test_price_collector.py` | Сохранение всех тикеров, общий timestamp, частичный сбой | Фейковый провайдер цен + SQLite in-memory |
| `test_price_repository.py` | Фильтр по тикеру, сортировка, последняя цена, период | SQLite in-memory |
| `test_price_query_service.py` | 404-сценарий, валидация периода | SQLite in-memory |
| `test_api.py` | Коды ответов, формат JSON, обязательность `ticker` | `dependency_overrides` с фейковым сервисом |

## Конфигурация

Все настройки задаются переменными окружения (или файлом `.env`), см. `.env.example`.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `deribit` | Доступ к БД |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | Адрес БД (`db` в Docker) |
| `REDIS_URL` | `redis://localhost:6379/0` | Брокер Celery |
| `DERIBIT_BASE_URL` | `https://www.deribit.com/api/v2` | Базовый URL API биржи |
| `DERIBIT_TIMEOUT_SECONDS` | `10` | Таймаут HTTP-запроса к бирже |
| `PRICE_FETCH_INTERVAL_SECONDS` | `60` | Период сбора цен |

---

## Design decisions

### 1. Слоистая архитектура: client → service → repository → API
Каждый слой отвечает за одно: `DeribitClient` знает только HTTP биржи, `PriceRepository` —
только SQL, сервисы — бизнес-правила, роуты — HTTP-протокол (коды, схемы). Поэтому слои
тестируются по отдельности, и замена одного (например, другой биржи) не трогает остальные.

### 2. Нет глобальных переменных — фабрики и Dependency Injection
- FastAPI собирается функцией `create_app()` и запускается через `uvicorn --factory`.
  Engine создаётся в `lifespan` и хранится в `app.state`, а не в модуле.
- Сессия → репозиторий → сервис передаются через `Depends`. В тестах они подменяются
  через `dependency_overrides`.
- `DeribitClient` получает `aiohttp.ClientSession` в конструкторе, `PriceCollector` —
  провайдер цен, репозиторий и часы (`clock`). Всё можно подменить в тестах.
- **Осознанное исключение:** `app/worker/main.py` создаёт экземпляр Celery при импорте.
  Celery CLI (`celery -A ...`) требует готовый объект приложения и не умеет вызывать фабрику.
  Это единственное такое место, и вся настройка всё равно в фабрике `create_celery_app()`.
  Задачи объявлены через `@shared_task` и не зависят от конкретного экземпляра.

### 3. Цена хранится как `NUMERIC(20, 8)` и `Decimal`, а не `float`
`float` не может точно представить большинство десятичных дробей, а для финансовых данных
ошибки округления недопустимы. Ответ Deribit парсится с `json.loads(parse_float=Decimal)`,
чтобы точность не терялась даже на этапе разбора JSON. В API цена отдаётся **строкой**
(`"67047.58000000"`) — стандартное поведение Pydantic для `Decimal`, которое сохраняет точность
на стороне клиента (JavaScript-клиент потерял бы её на `number`).

### 4. Время — `BIGINT` с UNIX timestamp в секундах
Так требует ТЗ. Целое число не зависит от часовых поясов, фильтр по периоду — простое
сравнение чисел. `BIGINT` вместо `INTEGER` — чтобы не упереться в 2038 год.

### 5. Составной индекс `(ticker, timestamp)`
Все три запроса API фильтруют по `ticker` и сортируют или фильтруют по `timestamp`.
Составной индекс покрывает их все. При сборе раз в минуту таблица растёт на ~1 млн строк
в год на тикер, без индекса запросы деградировали бы.

### 6. Один timestamp на весь запуск сбора
Цены всех тикеров за один запуск получают одинаковое время, чтобы их можно было сопоставлять
между собой. Время берётся до запроса к бирже — это момент, к которому относится снимок.

### 7. Параллельные запросы и изоляция сбоев
Тикеры запрашиваются параллельно через `asyncio.gather` — поэтому выбран aiohttp. С
`return_exceptions=True` сбой одного тикера логируется, но не мешает сохранить остальные.
Все записи одного запуска сохраняются в одной транзакции.

### 8. Celery-задача синхронная, внутри `asyncio.run()`
Celery не поддерживает async-задачи нативно, поэтому задача — тонкая синхронная обёртка,
а вся логика асинхронная. Каждый `asyncio.run()` создаёт новый event loop, а соединения
asyncpg привязаны к loop, в котором созданы. Поэтому для воркера engine создаётся на один
запуск с `NullPool` и закрывается в `finally`. Раз в минуту это дёшево.

### 9. Redis как брокер, beat — отдельный контейнер
Celery не работает без брокера. Redis — самый простой вариант. В необязательном требовании ТЗ
было «два контейнера (приложение и БД)», но для Celery нужен брокер, поэтому контейнеров пять:
`api`, `worker`, `beat`, `db`, `redis`. Beat вынесен отдельно, потому что планировщик должен
быть ровно один: при масштабировании воркеров (`docker compose up --scale worker=3`) задачи
не начнут дублироваться. У задачи стоит `expires` = интервалу: если воркер лежал, накопившиеся
устаревшие задачи не выполнятся пачкой.

### 10. Валидация тикера через Enum
`ticker` объявлен как `Ticker(StrEnum)`, поэтому FastAPI сам вернёт `422` на отсутствующий или
неизвестный тикер, а Swagger покажет допустимые значения выпадающим списком. Добавить валюту —
одна строка в Enum: её начнут собирать и отдавать через API автоматически.

### 11. Ошибки домена → HTTP-коды только в роутах
Сервисы бросают доменные исключения (`PriceNotFoundError`, `InvalidPeriodError`) и ничего не
знают про HTTP. Перевод в `404`/`400` делает слой API. Так сервисы можно переиспользовать
не только из FastAPI.

### 12. Миграции через Alembic
Схема создаётся миграцией, а не `create_all()` при старте. Это воспроизводимо и позволяет
менять схему, не теряя данные. Миграции применяются при старте контейнера `api`.

### 13. Тесты без внешней инфраструктуры
Репозиторий и сервисы тестируются на SQLite in-memory, клиент — на локальном aiohttp-сервере,
API — с подменённым сервисом. Тесты проходят за доли секунды и не зависят от сети и от биржи.

## Что можно улучшить

- **Пагинация** (`limit` / `offset`) для `/prices` и `/by-date`: за год набегает ~525 тыс. записей
  на тикер. Сейчас не добавлена, чтобы точно соответствовать формулировке ТЗ «все данные».
- **Ретраи** запросов к Deribit с экспоненциальной задержкой (`autoretry_for` в Celery).
- **Интеграционные тесты** на реальном PostgreSQL (testcontainers) и CI в GitLab (`.gitlab-ci.yml`).
- **Метрики** (Prometheus): число успешных и неуспешных сборов, задержка ответа биржи.
