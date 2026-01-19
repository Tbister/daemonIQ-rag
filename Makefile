PY?=python3
VENV=.venv
ACT=source $(VENV)/bin/activate

setup:
	$(PY) -m venv $(VENV) && $(ACT) && pip install -U pip && pip install -r requirements.txt

qdrant-up:
	cd docker && docker compose -f qdrant.docker-compose.yml up -d

qdrant-down:
	cd docker && docker compose -f qdrant.docker-compose.yml down

run:
	$(ACT) && uvicorn app.main:app --reload --port 8000

ingest:
	curl -s -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{"force_rebuild":false}' | jq . || \
	curl -s -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{"force_rebuild":false}'

ingest-rebuild:
	curl -s -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{"force_rebuild":true}' | jq . || \
	curl -s -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{"force_rebuild":true}'

ask:
	curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{"q":"$(Q)","k":4}' | jq . || \
	curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{"q":"$(Q)","k":4}'

stream:
	curl -N -X POST localhost:8000/chat-stream -H 'Content-Type: application/json' -d '{"q":"$(Q)","k":2}'

retrieve:
	curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' -d '{"q":"$(Q)","k":4}' | jq . || \
	curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' -d '{"q":"$(Q)","k":4}'

# Observability stack management
otel-up:
	docker compose -f docker/docker-compose-observability.yml up -d
	@echo ""
	@echo "Observability stack started:"
	@echo "  Jaeger UI:   http://localhost:16686"
	@echo "  Prometheus:  http://localhost:9090"
	@echo "  Grafana:     http://localhost:3000 (admin/admin)"
	@echo ""

otel-down:
	docker compose -f docker/docker-compose-observability.yml down

otel-logs:
	docker compose -f docker/docker-compose-observability.yml logs -f

# Run with tracing enabled
run-traced:
	$(ACT) && ENABLE_TRACING=true uvicorn app.main:app --reload --port 8000
