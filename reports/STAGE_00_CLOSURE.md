# Stage 0 — closure record

**Status:** DONE. Closed 2026-09-29 (IST) by verifying Stage 0's acceptance checks against
what is actually stored on GitHub, not against the working directory.

## Why this file exists

Stage 0 ran on the laptop and pushed `main` (commit `52c0d0d`), but its final commit — the
stage report and the last `PROGRESS.md` update — never reached GitHub, so Stage 0 still
showed as unfinished. This session was asked to verify Stage 0 from the repository and
close it.

**Correction to the original instruction.** The closure was expected to say that the full
Stage 0 report was on the laptop and would be added later. That is not the case: this
session is running on the same Windows laptop (`C:\Projects\ipo-agent`), so
`reports/STAGE_00_REPORT.md` was available and is committed alongside this file. Nothing
about Stage 0 is deferred.

## Acceptance checks, verified against `origin/main`

Checks read the committed tree (`git ls-tree -r origin/main`), so they reflect what a fresh
clone or a cloud session receives.

| Acceptance criterion | Result |
|---|---|
| Repo on GitHub with all code and data | ✅ 72 files on `origin/main` — 15 `.py`, 16 `.csv`, 4 `.xlsx`, 6 `.joblib`, 15 `.md`, 7 `.json`, 7 `.txt` |
| …except PDFs | ✅ 0 files matching `*.pdf`, `rhp_pdfs/`, `_backup*`, `__pycache__`, `.env` |
| `data/verified_rhp_manifest.csv` has one row per PDF | ✅ 9 lines = header + **8 rows**, matching the 8 PDFs in the laptop's `rhp_pdfs/` |
| `requirements.txt` | ✅ present |
| `.gitignore` | ✅ present (blob `8c74e7a`) |
| `PLAN.md` | ✅ present |
| `PROGRESS.md` | ✅ present |
| `DECISIONS.md` | ✅ present |
| `CLAUDE.md` | ✅ present |
| `work` branch exists | ✅ created from `main` and pushed in this session |

A first pass reported `.gitignore` missing. That was a Git Bash artifact — MSYS path
conversion rewrote `origin/main:.gitignore` as `origin\main;.gitignore`. The tree listing
confirms the file is committed. Recorded here because the same trap will recur: on Windows,
prefer `git ls-tree` over `git cat-file -e <rev>:<dotfile>`, or set `MSYS2_ARG_CONV_EXCL='*'`.

## Not re-run

Stage 0 is laptop-only and was **not** re-executed. No files were regenerated: the
manifest, `requirements.txt`, `.gitignore`, `.gitattributes` and the OS-independence fixes
are exactly as Stage 0 left them. This session only verified and committed.

See `reports/STAGE_00_REPORT.md` for what Stage 0 actually did, including the manifest
contents and the full list of OS-independence fixes.
