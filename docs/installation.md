# Installation

Requires Python 3.11 or newer.

```bash
python3 -m pip install .
yao-geo route --text "Discover AI search questions"
```

Build community artifacts with `python3 scripts/package.py --target all --channel community`. Install a provider, unified, Codex, or Claude ZIP by safely extracting it into the target's skill directory. Each adapter contains one `SKILL.md`, runtime source, schemas, registry, project metadata, version, and legal notices.

The wrappers require the dependencies declared in `pyproject.toml`. For direct command-line use after extraction, create an isolated environment and install the extracted bundle before invoking its wrapper:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python scripts/run_route.py --help
```

Provider hosts may supply the same declared dependencies in their managed runtime. The install simulation provisions a fresh environment for every extracted ZIP and invokes its packaged wrapper there.

Run `python3 scripts/verify_packages.py` before distribution and `python3 scripts/install_simulation.py --target all` after building. Generated `dist/` archives and temporary installation roots are scratch outputs and remain uncommitted.
