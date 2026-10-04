PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.PHONY: doctor test setup up configure verify drift-check repair maintain demo integration down destroy
setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.lock.txt

doctor:
	$(PYTHON) scripts/doctor.py

test:
	$(PYTHON) -m unittest discover -s tests -v

up configure verify drift-check repair maintain demo integration down destroy:
	@echo "$@ is pending implementation; see STATUS.md. No resources changed." >&2
	@exit 2
