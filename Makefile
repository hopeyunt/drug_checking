.PHONY: up down build logs shell test train-model migrate

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f api worker

shell:
	docker compose exec api bash

# Обучить ML-модель локально (нужен Python + зависимости)
train-model:
	cd ml && python train.py

# Запустить тесты внутри контейнера
test:
	docker compose exec api pytest tests/ -v --cov=app --cov-report=term-missing

# Применить миграции (если используется Alembic)
migrate:
	docker compose exec api alembic upgrade head

# Создать суперпользователя
create-admin:
	docker compose exec api python -c "from app.core.init_db import create_admin; import asyncio; asyncio.run(create_admin())"

# Полный сброс (осторожно!)
reset:
	docker compose down -v
	docker compose up -d
