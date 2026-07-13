#!/bin/bash
# Babysitter for the 90-day backfill: relaunches the analysis after any crash,
# network outage, or sleep/wake cycle, until the queue is actually empty.
# Run it once (survives everything except the queue finishing or a budget stop):
#   nohup scripts/backfill_babysitter.sh >> /tmp/backfill_babysitter.log 2>&1 &
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate

SINCE="2026-04-13"

while :; do
  out=$(python -m cli.main analyze --since "$SINCE" --limit 1500 2>&1 | tail -1)
  echo "$(date '+%F %T') | $out"
  case "$out" in
    *"0 articles processed"*)
      echo "$(date '+%F %T') | queue empty (or budget/pause stop) — babysitter exiting"
      break
      ;;
  esac
  # crash or partial run: wait 2 minutes (lets a flaky network settle) and go again
  sleep 120
done
