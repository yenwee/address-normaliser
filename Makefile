.PHONY: help test run eval score benchmark validate clean-golden install setup-drive docker-up docker-down deploy

INPUT ?= tests/benchmark/input.xls
OUTPUT ?= tests/benchmark/new_output.xlsx

help:
	@echo "Address Normaliser - common commands"
	@echo ""
	@echo "  make install         Install Python dependencies"
	@echo "  make test            Run all unit tests"
	@echo ""
	@echo "  make run             Run pipeline on default input (tests/benchmark/input.xls)"
	@echo "  make run INPUT=foo.xls OUTPUT=out.xlsx   Run on custom file"
	@echo ""
	@echo "  make score           Score current output against golden answers"
	@echo "  make benchmark       Compare current output against frozen baseline"
	@echo "  make eval            Quality checks (13 automated checks)"
	@echo "  make validate        Generate client-facing validation report"
	@echo "  make clean-golden    Re-clean golden answers (apply current format rules)"
	@echo ""
	@echo "  make setup-drive     One-time: create Google Drive folder structure"
	@echo ""
	@echo "  make docker-up       Start Drive polling service (production)"
	@echo "  make docker-down     Stop Drive polling service"
	@echo ""
	@echo "  make deploy          Deploy to contabo-vps (pulls, rebuilds, restarts)"

install:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v

run:
	python cli.py $(INPUT) $(OUTPUT)

score:
	python scripts/score_against_golden.py $(OUTPUT)

benchmark:
	python scripts/benchmark.py $(OUTPUT) --verbose

eval:
	python scripts/evaluate.py $(OUTPUT)

validate:
	python scripts/generate_validation_report.py $(INPUT) $(OUTPUT) tests/benchmark/validation_report.xlsx

clean-golden:
	python scripts/clean_golden.py --dry-run
	@echo ""
	@echo "Re-run without --dry-run to apply: python scripts/clean_golden.py"

setup-drive:
	python scripts/setup_drive.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

deploy:
	ssh contabo-vps "cd /opt/address-normaliser && git pull && docker compose up -d --build"
