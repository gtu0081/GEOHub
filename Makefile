PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: install test eval verify package package-verify install-smoke ci clean

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest
	$(PYTHON) scripts/run_evals.py

eval:
	$(PYTHON) scripts/run_evals.py

verify:
	$(PYTHON) scripts/verify_repository.py

package:
	$(PYTHON) scripts/package.py --target all --channel community

package-verify: package
	$(PYTHON) scripts/verify_packages.py

install-smoke: package-verify
	$(PYTHON) scripts/install_simulation.py --target all

ci: verify test eval package-verify install-smoke

clean:
	rm -rf build dist .pytest_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
