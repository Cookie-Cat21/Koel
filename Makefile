# Thin DX entrypoint for Chime local ops.
PYTHON ?= python3

.PHONY: help install lint typecheck test migrate up-db down-db up down

help:
	@echo "Chime local targets:"
	@echo "  make install     Install package + dev deps"
	@echo "  make lint        Run ruff"
	@echo "  make typecheck   Run mypy"
	@echo "  make test        Run pytest"
	@echo "  make up / up-db  Start local Postgres (docker compose)"
	@echo "  make down / down-db  Stop local Postgres"
	@echo "  make migrate     Apply SQL migrations"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .

typecheck:
	mypy chime

test:
	pytest

migrate:
	$(PYTHON) -m chime.migrate

up-db:
	docker compose up -d

down-db:
	docker compose down

up: up-db

down: down-db
