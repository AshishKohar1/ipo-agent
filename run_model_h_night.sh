#!/usr/bin/env bash
# Task 1's night batch (H9). Three stages, STRICTLY SEQUENTIAL: every stage talks to NSE
# at a >=3 s gap (rule 5 / rule 9), and running two at once would halve that gap without
# either stage knowing. Each stage is independently resumable and safe to kill.
#
#   1. corporate actions for the 3y windows   (~331 symbols, ~17 min)
#   2. corrected 1y targets, the 229 rows the cache-only run could not price
#   3. corrected 3y targets
#
# Stages 2 and 3 fetch bhavcopies for dates not already on disk and walk up to 7 days
# forward past holidays, so they are the long half - hours, not minutes. That is why this
# is a night batch and not a session task.
set -u
cd "$(dirname "$0")" || exit 1
log() { echo "[$(TZ=Asia/Kolkata date '+%F %H:%M:%S IST')] $*"; }

log "STAGE 1/3 - corporate actions, 3y windows"
python model_h_targets.py --actions --horizon 3y
log "stage 1 exit $?"

log "STAGE 2/3 - corrected 1y targets (fetching)"
python model_h_targets.py --build --horizon 1y
log "stage 2 exit $?"

log "STAGE 3/3 - corrected 3y targets (fetching)"
python model_h_targets.py --build --horizon 3y
log "stage 3 exit $?"

log "ALL STAGES ATTEMPTED"
python model_h_targets.py --effects --horizon 1y
python model_h_targets.py --effects --horizon 3y
