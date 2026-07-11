# Thin DX entrypoint for Chime local ops.
PYTHON ?= python3

.PHONY: install lint typecheck test migrate up-db down-db

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
