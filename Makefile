# Pi Sensors Makefile

.PHONY: install dev dev-backend dev-frontend test lint format build up down logs

# --- Setup ---
install:
	@echo "Installing dependencies..."
	uv sync
	cd frontend && bun install

# --- Development ---
dev:
	@echo "Starting backend and frontend in development mode..."
	make -j 2 dev-backend dev-frontend

dev-backend:
	@echo "Starting FastAPI backend..."
	uv run uvicorn pi_sensors.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

dev-frontend:
	@echo "Starting Nuxt 4 frontend..."
	cd frontend && NUXT_PUBLIC_API_BASE=http://localhost:8000/api NUXT_API_BASE_INTERNAL=http://localhost:8000/api bun run dev

# --- Testing ---
test:
	@echo "Running backend tests..."
	uv run pytest --tb=short -v

# --- Quality ---
lint:
	@echo "Linting backend..."
	uv run ruff check .

format:
	@echo "Formatting backend..."
	uv run ruff format .

# --- Docker ---
up:
	@echo "Starting production stack..."
	docker compose up -d --build

down:
	@echo "Stopping production stack..."
	docker compose down

logs:
	docker compose logs -f

# --- Build ---
build:
	@echo "Building Docker images..."
	docker compose build
