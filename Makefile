# FitFuse — the few commands worth not retyping.
#
#     make demo    API + frontend together, for the presentation
#     make test    the whole suite
#     make lint    ruff over the Python, eslint over the web
#
# The team develops on Windows, where `make` is usually absent: demo.ps1 is
# the primary runner and this file is the macOS/Linux equivalent. Both start
# uvicorn WITHOUT --reload, because the file watcher can restart the backend
# mid-presentation (PERSON_B.md §8).
#
# Owner: Person B

.PHONY: demo api web test lint health

API_PORT ?= 8000
WEB_PORT ?= 5173

demo:
	@python -m uvicorn api.main:app --port $(API_PORT) & \
	 for i in $$(seq 1 30); do \
	   curl -sf http://localhost:$(API_PORT)/health >/dev/null && break || sleep 0.5; \
	 done; \
	 curl -sf http://localhost:$(API_PORT)/health || { echo "API never came up"; exit 1; }; \
	 echo ""; \
	 echo "  API   http://localhost:$(API_PORT)/health"; \
	 echo "  Demo  http://localhost:$(WEB_PORT)"; \
	 echo ""; \
	 cd web && npm run dev:live; \
	 kill %1

api:
	python -m uvicorn api.main:app --port $(API_PORT)

web:
	cd web && npm run dev:live

test:
	python -m pytest -q
	cd web && npm run lint

lint:
	python -m ruff check .
	cd web && npm run lint

health:
	curl -s http://localhost:$(API_PORT)/health
