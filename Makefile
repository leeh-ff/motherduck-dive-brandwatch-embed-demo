.PHONY: serve check install

VENV := .venv
PY := $(VENV)/bin/python

$(PY): requirements.txt
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements.txt
	touch $(PY)

install: $(PY)

# Run the app locally at http://localhost:8000 (no login; token from $TOKEN_FILE)
serve: $(PY)
	LOCAL_DEV=1 $(PY) app.py

# Confirm the token file really is svc_embed_caller's (needs the duckdb CLI)
check:
	python3 check_token.py
