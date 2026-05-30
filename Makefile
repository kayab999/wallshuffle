.PHONY: install setup test lint clean build

VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

install:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest ruff mypy

setup:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(MAKE) install
	# Install package in editable mode
	$(PIP) install -e .

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy wallshuffle

format:
	$(PYTHON) -m ruff format .

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f *.spec

build:
	./scripts/build_appimage.sh
