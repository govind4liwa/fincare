.PHONY: help install dev up down restart logs ps shell db-shell migrate makemigrations test test-cov lint format typecheck security clean reset-db seed

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Dependencies ---
install:  ## Install all dev dependencies into local venv
	python -m pip install --upgrade pip
	pip install -r requirements/dev.txt
	pre-commit install
	pre-commit install --hook-type commit-msg

# --- Docker stack ---
up:  ## Bring up local stack (Postgres + Redis + Django)
	docker compose up -d

down:  ## Stop and remove containers
	docker compose down

restart:  ## Restart all services
	docker compose restart

logs:  ## Tail logs of all services
	docker compose logs -f

ps:  ## Show running services
	docker compose ps

# --- Django shells ---
shell:  ## Open Django shell in web container
	docker compose exec web python manage.py shell

db-shell:  ## Open psql in db container
	docker compose exec db psql -U fincare -d fincare

# --- Migrations ---
makemigrations:  ## Create new migrations
	docker compose exec web python manage.py makemigrations

migrate:  ## Apply migrations
	docker compose exec web python manage.py migrate

check-migrations:  ## Verify no pending migrations
	docker compose exec web python manage.py makemigrations --check --dry-run

# --- Testing ---
test:  ## Run test suite
	docker compose exec web pytest

test-cov:  ## Run tests with coverage report
	docker compose exec web pytest --cov=apps --cov-report=term-missing --cov-report=html

# --- Code quality ---
lint:  ## Run all linters
	ruff check .
	black --check .
	isort --check-only .

format:  ## Auto-format code
	ruff check --fix .
	black .
	isort .

typecheck:  ## Run mypy
	mypy apps

security:  ## Run security checks
	bandit -c pyproject.toml -r apps
	safety check --file requirements/prod.txt

# --- Database utilities ---
reset-db:  ## DROP and recreate database (DESTRUCTIVE)
	docker compose down -v
	docker compose up -d db
	sleep 5
	docker compose up -d

seed:  ## Seed reference data (COA, tax codes)
	docker compose exec web python manage.py seed_coa
	docker compose exec web python manage.py seed_tax

# --- Cleanup ---
clean:  ## Remove Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
