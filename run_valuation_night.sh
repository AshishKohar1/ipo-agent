#!/usr/bin/env bash
# Priority 1 night batch. STRICTLY SEQUENTIAL - the laptop has ~8 GB of RAM and
# pdfplumber holds a few hundred MB per open document, so two of these at once thrashes
# (measured: nine python processes, 1.26 GB free, every job stalled). CLAUDE.md says
# process large jobs one item at a time, and that is why.
#
# Stage 1 waits for the SEBI download to print its closing summary, then extraction runs
# alone. Both stages are resumable and safe to kill.
set -u
cd "$(dirname "$0")" || exit 1
log() { echo "[$(date '+%F %H:%M:%S')] $*"; }
FETCHLOG="$1"

log "waiting for the SEBI download to finish"
until grep -q "rhp_valuation_fetch.csv:" "$FETCHLOG" 2>/dev/null; do sleep 60; done
log "download finished:"
grep "rhp_valuation_fetch.csv:" "$FETCHLOG" | tail -1

log "STAGE extract - one document at a time"
python -u -X utf8 rhp_valuation.py --stage extract
log "extract exit $?"

log "coverage:"
python -u -X utf8 rhp_valuation.py --coverage
log "DONE"
