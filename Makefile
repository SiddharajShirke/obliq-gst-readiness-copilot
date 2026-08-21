SHELL := /bin/bash

.PHONY: setup backend-install frontend-install test lint build dev seed demo-docs ingest cleanup-whatsapp clean

setup: backend-install frontend-install demo-docs

backend-install:
	python -m pip install -e './backend[dev]'

frontend-install:
	cd frontend && npm install

test:
	cd backend && pytest

lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint

build:
	python -m compileall -q backend/app scripts
	cd frontend && npm run build

dev:
	docker compose up --build

seed:
	python scripts/seed_demo.py

demo-docs:
	python scripts/generate_demo_documents.py

ingest:
	python scripts/ingest_knowledge.py

cleanup-whatsapp:
	python scripts/cleanup_vonage_demo_sessions.py

clean:
	rm -rf .runtime backend/.pytest_cache backend/.ruff_cache frontend/.next frontend/node_modules
