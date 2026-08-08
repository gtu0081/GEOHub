PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: install test verify package clean

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest

verify:
	$(PYTHON) scripts/verify_repository.py
	$(PYTHON) -m pytest

package:
	$(PYTHON) scripts/package_repository.py

clean:
	rm -rf build dist .pytest_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
