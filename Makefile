# Thin DX entrypoint for Chime local ops.
PYTHON ?= python3

.PHONY: help install lint typecheck test test-unit migrate up-db down-db up down up-web down-web factory-status factory-verify factory-scoreboard factory-refill factory-wave portfolio-sum

help:
	@echo "Chime local targets:"
	@echo "  make install     Install package + dev deps"
	@echo "  make lint        Run ruff"
	@echo "  make typecheck   Run mypy"
	@echo "  make test        Run pytest (honors DATABASE_URL if set)"
	@echo "  make test-unit   Run pytest with DATABASE_URL cleared (CI unit parity)"
	@echo "  make up / up-db  Start local Postgres (docker compose --wait)"
	@echo "  make down / down-db  Stop local Postgres"
	@echo "  make up-web      Postgres + dash (compose --profile web)"
	@echo "  make down-web    Stop profile web stack"
	@echo "  make migrate     Apply SQL migrations (waits for compose health)"
	@echo "  make factory-status      Board + scoreboard"
	@echo "  make factory-verify      ruff/mypy/pytest proof (+ portfolio_sum smoke)"
	@echo "  make portfolio-sum       Plan A portfolio_sum.py smoke (non-fatal)"
	@echo "  make factory-scoreboard  Refresh SCOREBOARD.json"
	@echo "  make factory-refill      Activate next epoch if current empty"
	@echo "  make factory-wave        Next ≤8 OPEN ids"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .

typecheck:
	mypy chime

test:
	pytest

test-unit:
	DATABASE_URL= pytest

migrate:
	@docker compose up -d --wait 2>/dev/null || true
	$(PYTHON) -m chime.migrate

up-db:
	docker compose up -d --wait

down-db:
	docker compose down

up: up-db

down: down-db

up-web:
	docker compose --profile web up -d --wait --build

down-web:
	docker compose --profile web down

factory-status:
	$(PYTHON) scripts/factory/loop_status.py

factory-verify:
	bash scripts/factory/verify.sh

# E10-O01: Plan A portfolio score smoke; '-' keeps make green on stub gaps.
portfolio-sum:
	-$(PYTHON) scripts/factory/portfolio_sum.py

factory-scoreboard:
	$(PYTHON) scripts/factory/update_scoreboard.py --write

factory-refill:
	$(PYTHON) scripts/factory/refill_board.py

factory-wave:
	$(PYTHON) scripts/factory/next_wave.py
