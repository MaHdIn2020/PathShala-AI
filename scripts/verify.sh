#!/usr/bin/env bash
# One command to check the whole repo. Prints only failures (token-cheap). Exit 0 = GREEN.
cd "$(dirname "$0")/.." || exit 2
fail=0
step() {
  name=$1; shift
  out=$("$@" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS  $name"; else echo "FAIL  $name"; echo "$out" | tail -n 25; fail=1; fi
}
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
step compile $PY -m compileall -q pathshala ingest eval mcp_server tests
step unit    $PY -m unittest discover -s tests -t . -q
if $PY -m ruff --version >/dev/null 2>&1; then step lint $PY -m ruff check pathshala ingest eval tests; else echo "SKIP  lint (ruff not installed)"; fi
if [ -f web/package.json ] && [ -d web/node_modules ]; then
  step web-lint  npm --prefix web run lint --if-present
  step web-build npm --prefix web run build
else echo "SKIP  web (no web/package.json or node_modules)"; fi
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then step smoke $PY scripts/smoke.py; else echo "SKIP  smoke (API not running on :8000)"; fi
if [ $fail -eq 0 ]; then echo "VERIFY: GREEN"; else echo "VERIFY: RED"; fi
exit $fail
