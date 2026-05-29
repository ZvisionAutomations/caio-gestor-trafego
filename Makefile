.PHONY: help install run test report lint

PYTHON ?= python
MYPY_FILES := agent/caio.py agent/tools/meta_ads.py agent/tools/whatsapp.py agent/tools/scheduler.py agent/workflows/analyze.py agent/workflows/optimize.py agent/workflows/approve.py agent/workflows/report.py

help:
	@echo "Caio — Gestor de Tráfego Raiz Vital"
	@echo ""
	@echo "Comandos:"
	@echo "  make install   Instala dependências"
	@echo "  make run       Inicia o scheduler do Caio (produção)"
	@echo "  make test      Executa todos os harnesses com mocks"
	@echo "  make report    Gera relatório diário manualmente (mock)"
	@echo "  make lint      Checa formatação e tipos"

install:
	pip install -r requirements.txt

run:
	@echo "Iniciando Caio — Gestor de Tráfego Raiz Vital..."
	$(PYTHON) -m agent.main

test:
	@echo "Executando harnesses..."
	$(PYTHON) scripts/run_harnesses.py

report:
	@echo "Gerando relatório diário (mock)..."
	$(PYTHON) harnesses/test_report.py

lint:
	$(PYTHON) -m ruff check agent/ harnesses/ scripts/
	$(PYTHON) -m mypy $(MYPY_FILES) --python-version 3.11 --ignore-missing-imports --follow-imports=skip --no-incremental
