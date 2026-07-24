.PHONY: help install install-backend install-frontend db-init dev-backend dev-frontend dev test clean

PYTHON ?= python3

help:
	@echo "FinHub - comandos:"
	@echo "  make install       Instala backend + frontend"
	@echo "  make db-init       Crea tablas DB"
	@echo "  make dev           Arranca backend (8000) + frontend (3000)"
	@echo "  make test          Ejecuta tests"
	@echo "  make clean         Limpia caches"

install: install-backend install-frontend

install-backend:
	cd backend && $(PYTHON) -m venv venv && . venv/bin/activate && pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

db-init:
	cd backend && . venv/bin/activate && python scripts/init_db.py

dev:
	@trap 'kill 0' INT; \
	(cd backend && . venv/bin/activate && uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && . venv/bin/activate && pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/finhub.db

