# Recovery on the new Mac — 2026-11-02

The Windows laptop's disk died. GitHub `main` was authoritative and complete for everything
tracked; what died with the disk was the gitignored bulk: `_local/`,
`data/rhp_text_cache/`, `data/bhavcopy_cache/`, `data/bhavcopy_raw_cache/`,
`_local/check_set_dump/` and `.venv`.

## Task 0 — the visibility decision

Recorded as **H51** in `DECISIONS.md`: the repository is public by the user's decision of
2026-11-02, and H47's "the repository stays private" condition (rules 1 and 2) is waived.
`CLAUDE.md` rule 8 now points at H51 rather than asserting an aggregate-only rule that no
longer holds. H51 tables all 27 `data/` files that carry raw NSE or niftyindices rows, with
row counts and host, and states the three things about the exposure that are easy to miss:
it is retroactive across all 383 commits, it is permanent, and it is wider than the data
files because `data/live_fetch_log.csv` holds every request's URL and timestamp.

## Task 1 — environment

| item | result |
|---|---|
| machine | macOS 26.6, arm64 |
| interpreter | Python 3.14.10 in `.venv` |
| `requirements.txt` | all 10 pins installed as prebuilt wheels; **no pin changed**, nothing built from source |
| `check_env.py` | **15/15 pass** |
| module self-tests | 53 modules run: **50 clean**, 3 failing only for want of the lost caches |
| live workflow | 45 runs since 27 Oct, **45 success, 0 failures** |

The three self-test failures, all the same root cause and none a logic or path defect:

| module | failing check | cause |
|---|---|---|
| `build_check_set` | every one is on disk | the 20 check-set PDFs were under `_local/` |
| `build_text_cache` | the work list is the 450 fetched documents (got 0) | `data/rhp_text_cache/` is empty |
| `check_set_pages` | all 20 are in the text cache | same |

They are the measurement Tasks 3 and 4 exist to satisfy, so they are deliberately not
patched; they must go green on their own once the PDFs and the cache are back.

### Live legs since 27 Oct

| date | email leg (IST) | day-end leg (IST) | audit |
|---|---|---|---|
| Tue 27 Oct | 14:46 | 19:34 | — |
| Wed 28 Oct | 14:47 | 19:33 | — |
| Thu 29 Oct | 14:46 | 19:33 | — |
| Fri 30 Oct | 14:46 | 19:33 | — |
| Sat 31 Oct | — | — | 16:14 (due 10:30) |

The email and day-end legs both arrive as `workflow_dispatch` — the external cron-job.org
trigger is what lands them on time — while GitHub's own `schedule` runs fire hours late and
exit green on the idempotency marker, which is the design. **No leg has failed since
27 Oct.** No run has fired for Mon 2 Nov yet; at the time of writing it is 01:00 IST and the
email leg is not due until 14:15.

## Task 2 — Model L local parity, no refit

`models/model_l_v1.1_thresholds.json` gives L1 >= 28.39x and L2 >= 54.02x (H17). The last
10 `prediction` rows of `data/predictions_log.csv`, re-scored locally through `score_l.py`:

| IPO | Total | logged L1/L2 | local L1/L2 | match |
|---|---|---|---|---|
| Tonbo Imaging India Limited | 80.78x | BID/BID | BID/BID | yes |
| Bonfiglioli Transmissions Limited | 15.25x | no/no | no/no | yes |
| Sahajanand Medical Technologies Limited | 5.01x | no/no | no/no | yes |
| Zetwerk Manufacturing Businesses Limited | 1.74x | no/no | no/no | yes |
| Paras Healthcare Limited | 1.16x | no/no | no/no | yes |
| Jio Platforms Limited | 11.17x | no/no | no/no | yes |
| EAAA India Alternatives Limited | 2.01x | no/no | no/no | yes |
| SFC Environmental Technologies Limited | 2.42x | no/no | no/no | yes |
| BLS Polymers Limited | 171.83x | BID/BID | BID/BID | yes |
| M. K. Sons Fine Jewels Limited | 3.68x | no/no | no/no | yes |

**10 of 10 match. 0 mismatches.** The Mac reproduces the live verdicts exactly.

### Tripwire, read-only

`data/tripwire_state.json` SHA-1 was identical before and after the run, so nothing was
written. Rule H19 + H24, `trigger_at` 2:

| target | window | delivered | promise | bids | under | consecutive | fired |
|---|---|---|---|---|---|---|---|
| L1 | 2026-10 | 85.71% | 90% | 49 | yes | 1 of 2 | **no** |
| L2 | 2026-10 | 72.22% | 80% | 36 | yes | 1 of 2 | **no** |

Both targets under-deliver and both are armed at 1 of 2. **No action, by design.**
