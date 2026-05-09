# DrugCheck

Сервис проверки лекарственных взаимодействий для врачей.

Врач вводит список препаратов пациента — система за секунды проверяет все пары на взаимодействия и классифицирует тяжесть: от лёгкого (mild) до противопоказанного (contraindicated). База взаимодействий построена на официальных FDA-инструкциях (openFDA).

---

## Зачем это нужно

При 5 препаратах у пациента нужно проверить 10 пар взаимодействий, при 10 препаратах — уже 45. Вручную это нереально за время приёма. Особенно когда пациент приходит с назначениями сразу от кардиолога, эндокринолога и невролога.

---

## Стек

| Слой | Технологии |
|---|---|
| Backend | FastAPI + PostgreSQL + SQLAlchemy (async) |
| Очереди | Celery + Redis |
| ML | scikit-learn (GradientBoosting), данные из openFDA |
| Дашборд | Streamlit |
| Мониторинг | Prometheus + Grafana |
| Деплой | Docker Compose |

---

## Как запустить

**Требования:** Docker, Docker Compose

```bash
# 1. Клонировать репозиторий
git clone https://github.com/hopeyunt/drug_checking.git
cd drug_checking

# 2. Создать .env из примера
cp .env.example .env

# 3. Запустить всё
docker compose up -d
```

Что поднимается:
- `http://localhost:8000/docs` — Swagger с API
- `http://localhost:8501` — дашборд
- `http://localhost:3000` — Grafana (логин admin / admin)
- `http://localhost:9090` — Prometheus

ML-модель обучается автоматически при первом запуске (`ml-init` сервис). Первый старт занимает 1–2 минуты.

---

## Архитектура

```
клиент (Streamlit)
       │
       ▼
FastAPI (REST API)
       │
       ├── PostgreSQL — пользователи, пациенты, история
       ├── Redis — очередь задач
       └── Celery Worker — асинхронная проверка взаимодействий
                │
                └── ML модель (.joblib)
```

Проверка взаимодействий работает асинхронно: POST /interactions/check возвращает id задачи, результат забирается через GET /interactions/check/{id}. Это позволяет не держать соединение открытым.

---

## ML-модель

**Классификатор:** GradientBoostingClassifier

**Данные:** официальные инструкции по применению препаратов из openFDA API — 402 уникальные пары, собранные скриптом `ml/collect_real_data.py`.

**Признаки (10 штук):**
- Фармакологические классы обоих препаратов
- CYP-ингибирование / индукция (метаболические взаимодействия)
- QT-риск, риск кровотечений, нефротоксичность
- Серотониновый синдром, узкий терапевтический индекс, одинаковый класс

**Классы тяжести:**
- `none` — нет взаимодействия
- `mild` — лёгкое, мониторинг не нужен
- `moderate` — умеренное, рекомендуется мониторинг
- `severe` — серьёзное, нужна коррекция доз
- `contraindicated` — совместный приём противопоказан

Переобучить модель на новых данных: `docker compose exec api python /ml/train.py`

---

## API (основные эндпоинты)

```
POST /api/v1/auth/register     — регистрация
POST /api/v1/auth/login        — логин (JWT)
POST /api/v1/interactions/check — проверка взаимодействий (async)
GET  /api/v1/interactions/check/{id} — результат проверки
GET  /api/v1/patients          — список пациентов
POST /api/v1/patients          — добавить пациента
GET  /api/v1/billing/balance   — баланс и уровень лояльности
POST /api/v1/billing/payment/create — пополнение баланса
```

Полная документация: `http://localhost:8000/docs`

---

## Биллинг

Freemium-модель с кредитной системой:
- При регистрации начисляется 50 кредитов
- Одна проверка стоит 5 кредитов (с учётом скидки по уровню)

**Программа лояльности** (пересчёт раз в месяц через Celery Beat):

| Уровень | Проверок за месяц | Скидка |
|---|---|---|
| Bronze | < 50 | 0% |
| Silver | 50–199 | 5% |
| Gold | ≥ 200 | 15% |

Оплата через ЮКасса. Без ключей в .env работает в тестовом режиме — кредиты начисляются без реальной оплаты.

---

## Тесты

```bash
docker compose exec api pytest tests/ -v --cov=app
```

~1 000 строк тестов: авторизация, биллинг, пациенты, взаимодействия, admin API, unit-тесты ML-сервиса.

---

## Структура проекта

```
drugcheck/
├── backend/
│   ├── app/
│   │   ├── api/v1/        — роуты (auth, interactions, patients, billing, admin)
│   │   ├── models/        — SQLAlchemy модели
│   │   ├── services/      — бизнес-логика
│   │   └── tasks/         — Celery задачи
│   └── tests/
├── dashboard/             — Streamlit-приложение
├── ml/
│   ├── train.py           — обучение модели
│   ├── collect_real_data.py — сбор данных из openFDA
│   └── data/              — тренировочные данные
├── monitoring/            — Prometheus + Grafana конфиги
├── docker-compose.yml
├── Makefile
└── .env.example
```
