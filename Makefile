.PHONY: test test-agent test-api test-ingest test-dashboard test-admin install help

help:
	@echo "TekWatch development targets"
	@echo ""
	@echo "  make test           Run all Python test suites"
	@echo "  make test-agent     Run agent collector tests (no venv needed)"
	@echo "  make test-api       Run API tests (requires: cd api && pip install -r requirements.txt)"
	@echo "  make test-ingest    Run ingest-consumer tests (no venv needed)"
	@echo "  make test-dashboard Run dashboard unit tests"
	@echo "  make test-admin     Run admin-portal unit tests"
	@echo "  make install        Install all Python dependencies per service"

test: test-agent test-ingest

test-agent:
	cd agent && python -m pytest tests/ -v --tb=short

test-api:
	cd api && python -m pytest tests/ -v --tb=short

test-ingest:
	cd ingest-consumer && python -m pytest tests/ -v --tb=short

test-dashboard:
	cd dashboard && npm test

test-admin:
	cd admin-portal && npm test

install:
	@echo "--- agent ---"
	cd agent && pip install -r requirements.txt
	@echo "--- api ---"
	cd api && pip install -r requirements.txt
	@echo "--- ingest-consumer ---"
	cd ingest-consumer && pip install -r requirements.txt
	@echo "--- dashboard ---"
	cd dashboard && npm ci
	@echo "--- admin-portal ---"
	cd admin-portal && npm ci
