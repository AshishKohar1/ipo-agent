#!/usr/bin/env bash
# Second extraction pass, at VALUATION_VERSION 1.2.0 (promoter shareholding added).
#
# It waits for the 1.1.0 pass to exit, then runs ALONE - 8 GB laptop, one heavy pdfplumber
# job at a time. The version-aware resume re-does every document, because a file whose
# rows came from two extractor versions is one nobody can date; the 1.1.0 rows stay on
# disk (the file is append-only) so nothing is lost.
#
# The wait uses PowerShell, NOT pgrep. `pgrep` does not exist in this Git Bash, so a
# `while pgrep ...` loop exits immediately and pass 2 would have started CONCURRENTLY -
# the exact thing this script exists to prevent. Verified: the check below returns 2 while
# the pass is running.
set -u
cd "$(dirname "$0")" || exit 1
log() { echo "[$(date '+%F %H:%M:%S')] $*"; }

running() {
  powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*rhp_valuation.py --stage extract*' }).Count" \
    2>/dev/null | tr -d ' \r\n'
}

log "waiting for the 1.1.0 extraction pass to exit (currently $(running) process(es))"
while [ "$(running)" != "0" ]; do sleep 60; done
log "pass 1 finished"

log "PASS 2 - extraction at 1.2.0, promoter shareholding included"
python -u -X utf8 rhp_valuation.py --stage extract
log "exit $?"

log "coverage:"
python -u -X utf8 rhp_valuation.py --coverage
log "review sheet + promoter cross-check:"
python -u -X utf8 rhp_valuation.py --review
log "DONE"
