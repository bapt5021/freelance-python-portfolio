#!/usr/bin/env bash
# Lance les tests des trois démonstrations. Crée l'environnement virtuel d'un projet s'il manque.
set -euo pipefail
cd "$(dirname "$0")"
status=0
for demo in excel-csv-cleaner log-report telegram-alert-bot; do
  echo "=== $demo ==="
  if [ ! -x "$demo/.venv/bin/python" ]; then
    python3 -m venv "$demo/.venv"
    "$demo/.venv/bin/pip" install -q -r "$demo/requirements-dev.txt"
  fi
  (cd "$demo" && MPLBACKEND=Agg .venv/bin/python -m pytest -q) || status=1
done
exit $status
