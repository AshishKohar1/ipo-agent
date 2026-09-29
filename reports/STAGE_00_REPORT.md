# Stage 0 — Repository setup (laptop)

**Status:** AWAITING_USER. All setup work is done and `main` is on GitHub, but pushing the
`work` branch was blocked by the session's permission system. The user must run the four
git commands at the end of this report. The first Stage 1 session then confirms `work`
exists on GitHub and sets Stage 0 to `DONE`.

## What was done
- `check_env.py` 9/9 passed (before and after the changes below); git 2.54.0 present.
- Wrote `data/verified_rhp_manifest.csv`: 8 PDFs, every source URL confirmed by re-downloading it and matching SHA-256.
- Added `requirements.txt`, `.gitignore`, `.gitattributes`. Fixed OS-dependent code (list below). Added `PLAN.md`, `PROGRESS.md`, `DECISIONS.md`, `reports/`. Merged `CLAUDE.md`.
- `git init`, first commit `52c0d0d`, remote `origin` → github.com/AshishKohar1/ipo-agent, **`main` pushed**.
- **Not done:** creating and pushing branch `work` (blocked; see Open issues).

## Key numbers

| Item | Value |
|---|---|
| `check_env.py` | 9/9 PASS |
| Files committed | 72 (2.0 MB total) |
| Largest file | 210 KB (`checkpoints/target_1y_nifty50_tri.json`). **No file exceeds 50 MB** |
| PDFs, backups, caches in the repo | none (excluded by `.gitignore`) |
| Secret-pattern scan of the staged files | no matches |
| Manifest rows | 8 = one per PDF in `rhp_pdfs/` |
| Manifest URLs confirmed by SHA-256 | 8 / 8 |
| Manifest PDFs passing `_verify_is_prospectus()` | 8 / 8 |

### Manifest contents

| Company | Document | Pages | Source |
|---|---|---|---|
| Hyundai Motor India | RHP | 476 | SEBI |
| Hyundai Motor India | Prospectus | 476 | SEBI |
| Jupiter Life Line | RHP | 442 | SEBI |
| Jupiter Life Line | Prospectus | 442 | SEBI |
| CapitalNumbers Infotech (SME) | Prospectus | 369 | BSE SME |
| Syngene International | RHP | 401 | SEBI |
| Syngene International | Prospectus | 401 | SEBI |
| TD Power Systems (2011) | Prospectus (no RHP on SEBI) | 345 | SEBI |

Three of the eight, the Hyundai, Jupiter and Syngene prospectuses, had been downloaded only for the issue-size check, and their URLs had not been recorded. Their URLs were re-resolved from SEBI and accepted only because the re-download's SHA-256 matched the local file. SEBI requests were spaced ≥3 s apart.

### OS-independence fixes (step 5)

| File | Fix |
|---|---|
| `diag_cleanquery.py` | Hardcoded `os.chdir(r"C:\Projects\ipo-agent")` → the script's own directory |
| `build_target_and_stats.py`, `check_env.py` ×2, `clean_master.py` ×2, `fetch_rhp.py`, `run_overnight.py` ×2 | `read_text` / `write_text` without an encoding → explicit `encoding="utf-8"` (Windows defaults to cp1252, Linux to UTF-8) |
| `run_overnight.py`, `clean_master.py`, `recover_issue_dates.py`, `reconcile.py`, `build_target_and_stats.py`, `fetch_rhp.py` | Scripts assumed they were run from the repo root; `__main__` now changes to the script's own directory |
| `run_overnight.py` (`checkpoints/`, `run_log.txt`), `reconcile.py` (`ipo.db`), `build_target_and_stats.py` (`review/`) | Module-level cwd-relative paths → anchored to the file's location |
| `verify_rhp_resolvers.py`, `check_env.py` | stdout reconfigured to UTF-8 — Windows consoles crashed printing "₹" and "●" |
| new `.gitattributes` | `* text=auto`; `.xlsx`, `.joblib`, `.pdf` marked binary — line endings stay consistent between Windows and Linux checkouts |

No `os.path`, `subprocess`, shell or `.exe` calls exist in the code. Every module imports cleanly after the changes.

## Deviations from plan
- **Stage 0 status is `AWAITING_USER`, not `DONE`**: the `work` branch could not be created or pushed from this session.
- **`requirements.txt` needs Python ≥ 3.12**: numpy 2.5.1 requires it (pandas 3.0 requires ≥ 3.11). The cloud environment must provide 3.12 or newer; the laptop runs 3.14.5.
- Added `build_rhp_manifest.py` (the manifest generator, re-runnable) and `.gitattributes`. Neither is in the plan's list, but both serve steps 2 and 5.
- The first commit went to `main` with `PROGRESS.md` showing Stage 0 `IN_PROGRESS`, as the protocol requires. This report and the updated `PROGRESS.md` are **not yet committed**. The commands below commit them onto `work`.

## Open issues
1. **The `work` branch is not on GitHub** — push blocked by the session's permission rules. Run in `C:\Projects\ipo-agent`:
   ```bash
   git checkout -B work
   git add -A
   git commit -m "Stage 0: report and progress (AWAITING_USER until work is confirmed)"
   git push -u origin work
   ```
   `git checkout -B work` creates `work` from the current commit, or resets it there if it already exists locally. Nothing is lost either way, because everything since the first commit is uncommitted and is carried over.
2. Windows Application Control on the laptop blocks scikit-learn and `statsmodels.tsa`. That's irrelevant in the cloud, but Stage 1 should keep `check_env.py`'s checks OS-aware (PLAN.md Stage 1, step 2).
3. SME and mainboard issue-size definitions differ. IPOMatrix records SME size net of the market-maker reservation. See `SESSION_REPORT.md`, Task 5.
