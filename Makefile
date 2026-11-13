.PHONY: serve session

# Refresh the 24h embed session, then serve the page at http://localhost:8000
serve: session
	python3 serve.py

session:
	python3 make_session.py
