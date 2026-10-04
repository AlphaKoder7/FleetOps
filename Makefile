PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.PHONY: doctor test lint setup up configure verify drift-check repair maintain demo integration down destroy
setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.lock.txt

doctor:
	$(PYTHON) scripts/doctor.py

lint:
	$(PYTHON) scripts/checks.py

test:
	$(PYTHON) -m unittest discover -s tests -v

up down destroy:
	$(PYTHON) scripts/local.py $@ $(LOCAL_ARGS)

configure verify repair maintain:
	$(PYTHON) scripts/ops.py $@ $(OPS_ARGS)

drift-check:
	$(PYTHON) scripts/ops.py check

DEMO ?= all
demo:
	$(PYTHON) scripts/drills.py $(DEMO)

integration:
	$(PYTHON) scripts/integration.py
