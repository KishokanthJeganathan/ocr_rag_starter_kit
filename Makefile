.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down nuke logs ps migrate seed revision shell-db test lint fmt typecheck check gen gen-check

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up:  ## Build and start the local stack
	$(COMPOSE) up -d --build

down:  ## Stop the local stack
	$(COMPOSE) down

nuke:  ## Stop the stack and delete volumes (drops all data)
	$(COMPOSE) down -v

logs:  ## Tail service logs
	$(COMPOSE) logs -f

ps:  ## Show service status
	$(COMPOSE) ps

migrate:  ## Apply database migrations
	$(COMPOSE) run --rm api alembic upgrade head

seed:  ## Create the demo tenant + matter
	$(COMPOSE) run --rm api python -m scripts.seed

revision:  ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(m)"

shell-db:  ## Open psql as the superuser
	$(COMPOSE) exec postgres psql -U postgres -d ocr_rag

test:  ## Run backend tests (needs `make up` first)
	cd backend && uv run pytest -q

lint:  ## Check lint + formatting
	cd backend && uv run ruff check . && uv run ruff format --check .

fmt:  ## Auto-fix lint + format
	cd backend && uv run ruff check --fix . && uv run ruff format .

typecheck:  ## Run mypy
	cd backend && uv run mypy app

check: lint typecheck test  ## Run every backend check

gen:  ## Generate sample fixtures into fixtures/ (make gen N=5)
	cd generator && uv run python -m generator make --type nda --count $(or $(N),5) --out ../fixtures

gen-check:  ## Lint + type-check + test the generator
	cd generator && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
