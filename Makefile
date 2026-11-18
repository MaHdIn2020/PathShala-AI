.PHONY: setup db api web verify ingest eval
setup:   ; bash scripts/setup.sh
db:      ; docker compose up -d db
api:     ; . .venv/bin/activate && uvicorn pathshala.api:app --reload --port 8000
web:     ; npm --prefix web run dev
verify:  ; bash scripts/verify.sh
ingest:  ; . .venv/bin/activate && python -m ingest.run
eval:    ; . .venv/bin/activate && python -m eval.run_eval && python -m eval.run_eval --baseline --out eval/results_baseline.json
