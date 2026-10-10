"""
rhp_night_batch.py — PLAN.md Stage 15b: the unattended H6 extraction batch.

Queue: every mainboard IPO in `master_with_symbols.csv` that has an `excess_1y` label and
no `exclude_reason`. Per company:

    resolve from SEBI (BSE SME for SME) -> download -> verify _verify_is_prospectus() and
    record SHA-256 -> extract the H6 fields -> reconcile -> write to the database ->
    DISCARD the PDF

Batch rules (H9 and the Stage 15b brief):
  * minimum 3 s between SEBI requests
  * per-company status in `data/rhp_progress.csv`, written after every company
  * commit every 5 companies
  * fully resumable — restarting skips anything already `done` or `failed`
  * transient errors (timeout, connection, 5xx) retried up to 3 times with backoff
  * after two identical non-transient failures on one company: mark failed, move on
  * if 5 consecutive companies fail: STOP and report — the site has probably changed
  * free disk space checked before starting and before every download; stop cleanly
    below 2 GB
  * safe to kill at any moment: the progress file and the observations file are appended
    per company, never held in memory to the end

On SHA-256: for a document already in `data/verified_rhp_manifest.csv` the hash is
*verified* against the manifest and a mismatch refuses extraction (hard rule 4). For a
document seen for the first time there is nothing to verify against, so the hash is
*recorded* — which is what makes the value re-checkable later, since the PDF itself is
discarded.

    python rhp_night_batch.py                 # run / resume
    python rhp_night_batch.py --limit 5       # a short pilot
    python rhp_night_batch.py --status        # what is left
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import argparse
import gc
import hashlib
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from extract import base as B          # noqa: E402
from extract import h6                 # noqa: E402

PROGRESS = ROOT / "data" / "rhp_progress.csv"
OBS = ROOT / "reports" / "h6_batch_observations.csv"
TMP = ROOT / "_local" / "rhp_fetched" / "_batch_tmp"
# Raised from 3.2 s to 5 s. The first run stopped at 278 of 485 when SEBI began refusing
# connections and five in a row tripped the breaker — which is the breaker working, but the
# trigger was throttling rather than the site changing.
MIN_GAP_S = 5.0
MIN_FREE_GB = 2.0
MAX_TRANSIENT_RETRIES = 3
MAX_CONSECUTIVE_FAILS = 5
COMMIT_EVERY = 5

# THROTTLING IS NOT FAILURE, and conflating the two is what stopped the first run 207
# companies early. A 429, a 503 or a dropped connection means "slow down"; a missing
# document means "this one is not here". They are counted separately: throttling backs off
# and does NOT advance the consecutive-failure breaker, while a genuine failure does.
THROTTLE = ("429", "503", "502", "504", "too many requests", "rate limit", "retry-after",
            "connectionerror", "connection aborted", "connection reset", "reset by peer",
            "max retries exceeded", "timeout", "timed out", "read timed out",
            "remotedisconnected", "temporarily")
TRANSIENT = THROTTLE + ("ssl",)
# Backoff for throttling: 10 s, 30 s, 90 s, 270 s, then hold at 600 s. Cumulative, so a
# throttled site is given real time to recover instead of being hammered on a fixed gap.
THROTTLE_BACKOFF_S = (10, 30, 90, 270, 600)
MAX_THROTTLE_PAUSES = 12        # ~30 min of cumulative backoff before giving up for tonight

PROGRESS_COLS = ["company", "isin", "listing_date", "segment", "status", "doc_type",
                 "source", "url", "sha256", "pages", "n_ok", "n_ambiguous",
                 "n_not_applicable", "n_not_found", "secs", "attempts", "note", "ran_at"]


# ---------------------------------------------------------------- queue
def build_queue() -> pd.DataFrame:
    m = pd.read_csv(ROOT / "master_with_symbols.csv")
    h = pd.read_csv(ROOT / "holding_target.csv")
    labelled = set(h.loc[h["H_label"].notna(), "isin"].dropna())
    q = m[m["exclude_reason"].isna()].copy()
    q = q[q["isin"].isin(labelled)]
    q["segment"] = "mainboard"          # the master holds no SME rows; SME uses BSE_SME
    q = q.sort_values("listing_date", ascending=False)
    return q[["company", "isin", "listing_date", "segment"]].reset_index(drop=True)


def load_progress() -> pd.DataFrame:
    if PROGRESS.exists():
        p = pd.read_csv(PROGRESS)
        for c in PROGRESS_COLS:
            if c not in p:
                p[c] = None
        return p[PROGRESS_COLS]
    return pd.DataFrame(columns=PROGRESS_COLS)


def append_progress(row: dict) -> None:
    """One row, appended and flushed immediately — the batch must be killable."""
    df = pd.DataFrame([{c: row.get(c) for c in PROGRESS_COLS}])
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROGRESS, mode="a", header=not PROGRESS.exists(), index=False,
              encoding="utf-8")


def append_obs(rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    OBS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OBS, mode="a", header=not OBS.exists(), index=False, encoding="utf-8")


# ---------------------------------------------------------------- environment
def free_gb(path: Path = ROOT) -> float:
    return shutil.disk_usage(path).free / 1e9


def git(*args: str) -> tuple[int, str]:
    """Git is called with separate arguments, never chained with && (decision F2)."""
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def commit(n_done: int) -> None:
    git("add", "data/rhp_progress.csv", "reports/h6_batch_observations.csv")
    code, out = git("commit", "-q", "-m",
                    f"Stage 15b night batch: {n_done} companies processed\n\n"
                    "Automated checkpoint from rhp_night_batch.py. PDFs discarded after "
                    "extraction; every value carries its page, source line, document URL "
                    "and SHA-256.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    if code == 0:
        git("push", "-q", "origin", "main")
        print(f"    [checkpoint committed and pushed at {n_done} companies]", flush=True)
    elif "nothing to commit" not in out:
        print(f"    [commit skipped: {out[:120]}]", flush=True)


# ---------------------------------------------------------------- one company
def page_texts_all(path: Path) -> list[str]:
    """Every page's text. The whole document is read on purpose: several H6 fields record
    the ABSENCE of a phrase as a real 0 (dual-class voting, emphasis of matter), and that
    conclusion is only valid if the entire document was searched."""
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages):
            try:
                out.append(pg.extract_text() or "")
            except Exception:
                out.append("")
            try:
                pg.flush_cache()
                pg.get_textmap.cache_clear()
            except Exception:
                pass
            if i % 100 == 99:
                gc.collect()
    return out


def manifest_hashes() -> dict[str, str]:
    p = ROOT / "data" / "verified_rhp_manifest.csv"
    if not p.exists():
        return {}
    m = pd.read_csv(p)
    return {f"{r.company}|{r.doc_type}": r.sha256 for r in m.itertuples()}


def process(row, known: dict[str, str]) -> dict:
    """Fetch, verify, extract, discard. Returns the progress row."""
    import fetch_rhp as FR
    t0 = time.time()
    out = {"company": row.company, "isin": row.isin, "listing_date": row.listing_date,
           "segment": row.segment, "ran_at": str(pd.Timestamp.now()), "attempts": 1}

    sources = ("SEBI",) if row.segment == "mainboard" else ("BSE_SME",)
    rec = FR.fetch_for_company(row.company, row.isin, "RHP",
                               listing_date=row.listing_date, sources=sources)
    out.update({"doc_type": rec.doc_type, "source": rec.source, "url": rec.url,
                "sha256": rec.sha256, "pages": rec.pages, "note": rec.note})
    if rec.status != "ok" or not rec.local_path:
        out["status"] = rec.status
        out["secs"] = round(time.time() - t0, 1)
        return out

    pdf = Path(rec.local_path)
    try:
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        key = f"{row.company}|{rec.doc_type}"
        if key in known and known[key] != sha:
            out.update({"status": "sha256_mismatch", "sha256": sha,
                        "note": f"manifest expects {known[key][:16]}, got {sha[:16]} — "
                                "refusing to extract (hard rule 4)"})
            return out
        out["sha256"] = sha
        verified = "verified against the manifest" if key in known else "recorded (first sight)"

        pages = page_texts_all(pdf)
        toc = B.parse_toc(pdf, len(pages))
        off = B.measure_offset(pdf, len(pages))
        doc = B.Doc(pdf, row.company, rec.doc_type, sha, rec.url, len(pages), off, toc)
        vals = h6.extract(doc, pages)
        core = [v for v in vals if v.variable in h6.FIELDS]
        append_obs([v.as_row() for v in vals])
        out.update({
            "status": "done", "pages": len(pages),
            "n_ok": sum(v.status == "ok" for v in core),
            "n_ambiguous": sum(v.status == "ambiguous" for v in core),
            "n_not_applicable": sum(v.status == "not_applicable" for v in core),
            "n_not_found": sum(v.status == "not_found" for v in core),
            "note": f"offset {off:+d}, toc {len(toc)} entries, sha256 {verified}",
        })
        del pages
    finally:
        # The PDF is discarded whatever happened. Any value can be re-checked by
        # re-fetching the URL and matching the SHA-256 recorded above.
        try:
            if pdf.exists() and TMP in pdf.parents:
                pdf.unlink()
            elif pdf.exists() and pdf.parent.name == "rhp_fetched":
                pdf.unlink()
        except Exception as e:
            out["note"] = f"{out.get('note', '')} | PDF not deleted: {e}"
        gc.collect()
    out["secs"] = round(time.time() - t0, 1)
    return out


def is_transient(msg: str) -> bool:
    m = (msg or "").lower()
    return any(k in m for k in TRANSIENT)


def is_throttle(msg: str) -> bool:
    """Is the source asking us to slow down, rather than telling us a document is absent?"""
    m = (msg or "").lower()
    return any(k in m for k in THROTTLE)


# ---------------------------------------------------------------- main loop
def clear_retryable() -> int:
    """Priority 2b: re-queue the companies whose only problem was a refused connection.

    Those were never missing documents — the five recorded as `fetch_error` are
    Anupam Rasayan, Craftsman Automation, Easy Trip Planners, Kalyan Jewellers and Laxmi
    Organic. Their progress rows are removed so the resumable queue picks them up again.
    """
    if not PROGRESS.exists():
        return 0
    p = pd.read_csv(PROGRESS, keep_default_na=False, na_values=[""])
    note = p["note"].astype(str)
    retryable = (note.str.contains("ConnectionError|Max retries|Timeout|timed out",
                                   case=False, regex=True)
                 & ~p["status"].isin(["done"]))
    k = int(retryable.sum())
    if k:
        p[~retryable].to_csv(PROGRESS, index=False, encoding="utf-8")
        print(f"re-queued {k} company/companies whose fetch was refused rather than missing:")
        for c in p.loc[retryable, "company"]:
            print(f"    - {c}")
    return k


def main(limit: int | None = None, status_only: bool = False,
         retry_failed: bool = False) -> None:
    if retry_failed:
        clear_retryable()
    q = build_queue()
    prog = load_progress()
    # `source_unresolved` counts as settled. It is a deterministic outcome — SEBI's archive
    # has no document matching the company name and filing window — not a transient error,
    # and the reason is recorded per company. Leaving it unsettled made every restart retry
    # the same unresolvable companies before reaching new ones, so a resumed run could
    # never finish the queue. Delete those rows from data/rhp_progress.csv to retry them
    # after a resolver improvement.
    settled = set(prog.loc[prog["status"].isin(
        ["done", "failed", "sha256_mismatch", "source_unresolved", "not_a_prospectus"]),
        "company"])
    todo = q[~q["company"].isin(settled)]

    print(f"queue {len(q)} | settled {len(settled)} | to do {len(todo)} | "
          f"free disk {free_gb():.1f} GB")
    if status_only:
        if len(prog):
            print(prog["status"].value_counts().to_string())
        return
    if free_gb() < MIN_FREE_GB:
        print(f"STOP: free disk {free_gb():.1f} GB is below the {MIN_FREE_GB} GB floor")
        return

    known = manifest_hashes()
    TMP.mkdir(parents=True, exist_ok=True)
    consecutive, n_done, last = 0, 0, 0.0
    throttle_pauses = 0

    for row in todo.itertuples(index=False):
        if limit is not None and n_done >= limit:
            print(f"\nstopping at the --limit of {limit} companies")
            break
        if free_gb() < MIN_FREE_GB:
            print(f"\nSTOP: free disk {free_gb():.1f} GB below the {MIN_FREE_GB} GB floor")
            break

        gap = MIN_GAP_S - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
        last = time.time()

        res, attempt, seen_msgs = None, 0, []
        throttled_this_company = 0
        while attempt < MAX_TRANSIENT_RETRIES:
            attempt += 1
            try:
                res = process(row, known)
                if res.get("status") == "done":
                    break
                msg = str(res.get("note") or res.get("status"))
                if not is_transient(msg):
                    break                      # a real refusal, not worth retrying
                seen_msgs.append(msg)
                if is_throttle(msg):
                    throttle_pauses += 1
                    throttled_this_company += 1
                    back = THROTTLE_BACKOFF_S[min(throttle_pauses - 1,
                                                  len(THROTTLE_BACKOFF_S) - 1)]
                    print(f"    THROTTLED ({msg[:70]}) — backing off {back}s "
                          f"(pause {throttle_pauses}/{MAX_THROTTLE_PAUSES}); this does NOT "
                          f"count toward the failure breaker", flush=True)
                    if throttle_pauses >= MAX_THROTTLE_PAUSES:
                        print(f"\nSTOP: {throttle_pauses} throttle pauses — SEBI is rate "
                              f"limiting persistently. Stopping cleanly; the queue is "
                              f"resumable and nothing is lost.", flush=True)
                        break
                    attempt -= 1               # a throttle is not one of the 3 real retries
                else:
                    back = MIN_GAP_S * (2 ** attempt)
                    print(f"    transient ({msg[:60]}), retry {attempt} in {back:.0f}s",
                          flush=True)
                time.sleep(back)
                last = time.time()
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                seen_msgs.append(msg)
                if not is_transient(msg):
                    res = {"company": row.company, "isin": row.isin,
                           "listing_date": row.listing_date, "segment": row.segment,
                           "status": "failed", "attempts": attempt,
                           "note": msg[:280], "ran_at": str(pd.Timestamp.now())}
                    # two identical non-transient failures on one company: stop trying it
                    if seen_msgs.count(msg) >= 2:
                        break
                    continue
                time.sleep(MIN_GAP_S * (2 ** attempt))
                last = time.time()
        if res is None:
            res = {"company": row.company, "isin": row.isin, "status": "failed",
                   "segment": row.segment, "listing_date": row.listing_date,
                   "attempts": attempt, "ran_at": str(pd.Timestamp.now()),
                   "note": "; ".join(seen_msgs)[:280] or "no result"}
        res["attempts"] = attempt
        if res.get("status") != "done":
            res["status"] = res.get("status") or "failed"
        append_progress(res)

        ok = res.get("status") == "done"
        # A company abandoned purely because the source was throttling is NOT a failure of
        # that company, so it must not advance the breaker — otherwise five throttles in a
        # row stop a run that would have completed, which is exactly what happened at 278.
        throttle_only = (not ok) and throttled_this_company > 0 and is_throttle(
            str(res.get("note") or ""))
        if ok or throttle_only:
            consecutive = 0
        else:
            consecutive += 1
        n_done += 1
        flag = "" if ok else "   <-- FAILED"
        print(f"  [{n_done:4d}/{len(todo)}] {str(row.company)[:34]:36s} "
              f"{res.get('status'):16s} ok={res.get('n_ok') or 0:2} "
              f"amb={res.get('n_ambiguous') or 0:2} miss={res.get('n_not_found') or 0:2} "
              f"{res.get('secs') or 0:5.0f}s{flag}", flush=True)
        if not ok:
            print(f"        {str(res.get('note'))[:150]}", flush=True)

        if n_done % COMMIT_EVERY == 0:
            commit(len(settled) + n_done)

        if throttle_pauses >= MAX_THROTTLE_PAUSES:
            break
        if consecutive >= MAX_CONSECUTIVE_FAILS:
            print(f"\nSTOP: {consecutive} consecutive GENUINE failures (throttling is "
                  f"counted separately and did not contribute) — the source has probably "
                  f"changed. Nothing further attempted.")
            break

    commit(len(settled) + n_done)
    p = load_progress()
    print(f"\nprocessed this run: {n_done} | total settled: {len(p)}")
    if len(p):
        print(p["status"].value_counts().to_string())
    print(f"free disk {free_gb():.1f} GB")


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-queue companies whose fetch was refused (Priority 2b)")
    a = ap.parse_args()
    main(a.limit, a.status, a.retry_failed)
