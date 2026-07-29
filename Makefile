SHELL := /bin/bash
SOURCE_DB ?= ./ldxp_crawler.db

.PHONY: up prod-up down logs ps test-api test-pipeline build-web release-check import-db seed

up:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

prod-up:
	python scripts/production_preflight.py
	docker compose --profile production up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

test-api:
	cd apps/api && python -m pytest -q

test-pipeline:
	cd pipeline && python -m pytest -q

build-web:
	cd apps/web && npm ci && npm run typecheck && npm run build

release-check:
	bash scripts/validate_release.sh

import-db:
	docker compose --profile tools run --rm importer python sync_ldxp.py --source-db /workspace/$(SOURCE_DB)

seed:
	docker compose exec api python -m app.seed
