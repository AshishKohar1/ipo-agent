r"""
repo_paths.py — turn a recorded relative path into a Path that works on this OS.

Every `path` column in this repo's CSVs (`data/rhp_valuation_fetch.csv`,
`reports/rhp_check_set_docs.csv`, `data/rhp_progress.csv`) was written on Windows and
reads `_local\rhp_valuation\Polycab_India_Ltd.pdf`. On POSIX a backslash is an ordinary
filename character, so `ROOT / that` is a single 38-character filename that cannot
exist — and because every caller then filters on `.exists()` or `TC.get(...) is None`,
the failure is SILENT: the work list comes back empty and the job reports "nothing to
do" and exits 0. Found on the macOS move, 2026-11-02.

One function, so the separator is handled in one place and a new caller cannot
reintroduce the bug by forgetting it. Writers keep using whatever `os.sep` gives them;
only readers come through here.
"""
from __future__ import annotations
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parent


def repo_file(p) -> Path:
    """`p` as recorded in a CSV (either separator, relative to the repo) -> absolute."""
    s = str(p).strip().replace("\\", "/")
    q = PurePosixPath(s)
    return q if q.is_absolute() else ROOT / q


def self_test() -> int:
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] a Windows-recorded path resolves to the file it names")
    win = r"_local\rhp_valuation\Polycab_India_Ltd.pdf"
    got = repo_file(win)
    chk("the backslashes become path components, not one filename",
        got.name == "Polycab_India_Ltd.pdf", got.name)
    chk("and the parent is the directory the CSV meant",
        got.parent == ROOT / "_local" / "rhp_valuation", got.parent)
    chk("this is the bug the helper exists for: the naive form is ONE file",
        (ROOT / win).name == win, (ROOT / win).name)

    print("\n[2] a POSIX-recorded path is unchanged")
    chk("same answer either way",
        repo_file("_local/rhp_valuation/X.pdf") == repo_file(r"_local\rhp_valuation\X.pdf"))
    chk("nested components survive",
        repo_file("data/rhp_text_cache/a/b.json")
        == ROOT / "data" / "rhp_text_cache" / "a" / "b.json")

    print("\n[3] edge cases a CSV actually produces")
    chk("surrounding whitespace is stripped",
        repo_file("  _local/x.pdf  ") == ROOT / "_local" / "x.pdf")
    chk("an absolute path is left alone",
        repo_file("/tmp/x.pdf") == Path("/tmp/x.pdf"))
    chk("the result is always absolute", repo_file("a/b.pdf").is_absolute())

    print("\n[4] the Windows reading of the same string agrees")
    chk("PureWindowsPath sees the same components",
        PureWindowsPath(win).parts == ("_local", "rhp_valuation",
                                       "Polycab_India_Ltd.pdf"))

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(self_test())
