.PHONY: help install run test report lint

PYTHON := python3

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
	@echo ""
	@echo "=== test_analyze ==="
	$(PYTHON) harnesses/test_analyze.py
	@echo ""
	@echo "=== test_report ==="
	$(PYTHON) harnesses/test_report.py
	@echo ""
	@echo "=== test_approve ==="
	$(PYTHON) harnesses/test_approve.py
	@echo ""
	@echo "Todos os harnesses concluídos."

report:
	@echo "Gerando relatório diário (mock)..."
	$(PYTHON) harnesses/test_report.py

lint:
	ruff check agent/ harnesses/
	mypy agent/ --ignore-missing-imports
