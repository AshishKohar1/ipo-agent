#!/usr/bin/env bash
# Phase 2.5. The 15 symbols recovered in 2.1, plus the 18 rows the earlier batch could not
# price. Four stages, STRICTLY SEQUENTIAL - every one talks to NSE at a >=3 s gap and two
# at once would halve it without either knowing (rule 9).
#
# Each stage is independently resumable and safe to kill at any moment (H9).
set -u
cd "$(dirname "$0")" || exit 1
log() { echo "[$(TZ=Asia/Kolkata date '+%F %H:%M:%S IST')] $*"; }

log "STAGE 1/4 - corporate actions, 1y windows (new rows only)"
python model_h_targets.py --actions --horizon 1y
log "stage 1 exit $?"

log "STAGE 2/4 - corporate actions, 3y windows (new rows only)"
python model_h_targets.py --actions --horizon 3y
log "stage 2 exit $?"

log "STAGE 3/4 - corrected 1y targets"
python model_h_targets.py --build --horizon 1y
log "stage 3 exit $?"

log "STAGE 4/4 - corrected 3y targets"
python model_h_targets.py --build --horizon 3y
log "stage 4 exit $?"

log "ALL STAGES ATTEMPTED"
python model_h_targets.py --effects --horizon 1y
python model_h_targets.py --effects --horizon 3y
