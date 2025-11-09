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
	$(ACT) && cd app && uvicorn main:app --reload --port 8000

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
