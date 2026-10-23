"""
failover.py — one attempt per host, then move to the next source. H47 rule 5.

The rule this enforces, and the line it will not cross
------------------------------------------------------
H47 lets this project keep reading NSE and niftyindices, whose terms prohibit automated
collection, on six conditions. The fifth is the one with teeth:

> Every NSE/niftyindices fetch has an automatic failover to BSE/Chittorgarh. A block
> (403/connection refusal) is never worked around — the pipeline fails over and reports it.

So a blocked host gets **exactly one attempt per run**. No retry loop, no second request
with a different User-Agent, no pause-and-try-again, no alternate route. Those are
circumventions, and the difference between failing over and working around is the whole of
this decision's integrity.

A **block** (`BLOCKED`) and a **fault** (`FAILED`) are kept apart on purpose:

* `BLOCKED` — HTTP 401/403/429, or the connection refused or reset. The host has answered.
  That answer is final for this run, and it is reported in the run summary by name.
* `FAILED` — a timeout, a 5xx, a parse error, an empty payload. The host did not answer, or
  answered with something broken. This is an ordinary fault and the chain moves on, but it
  is not reported as a block, because calling a timeout a block would make the term useless
  on the day it matters.

Neither is retried here. A retry policy belongs to the caller, and no caller may retry a
`BLOCKED` source.

    from failover import chain, Source
    res = chain("live subscription", [Source("NSE", nse_fn), Source("Chittorgarh", cg_fn)])
    if res.ok:
        use(res.value)
    print(res.summary)        # "NSE blocked - failed over to Chittorgarh"
"""
from __future__ import annotations
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dataclasses import dataclass, field
from typing import Any, Callable

BLOCKED_STATUS = {401, 403, 429}
# Exception type names that mean "the host refused or dropped the connection". Matched by
# NAME so this module needs no requests/urllib3 import and cannot drift with their layout.
BLOCKED_EXC = {"ConnectionRefusedError", "ConnectionResetError", "ProxyError",
               "SSLError", "TooManyRedirects"}
FAULT_EXC = {"Timeout", "ReadTimeout", "ConnectTimeout", "ConnectionError",
             "ChunkedEncodingError", "JSONDecodeError", "ValueError", "KeyError"}


class Blocked(Exception):
    """Raise from a source function when the host has refused this client."""


@dataclass
class Source:
    name: str
    fn: Callable[[], Any]
    host: str = ""


@dataclass
class Attempt:
    name: str
    state: str                      # ok | blocked | failed
    detail: str = ""


@dataclass
class Result:
    item: str
    ok: bool
    value: Any = None
    used: str = ""
    attempts: list = field(default_factory=list)
    blocked: list = field(default_factory=list)

    @property
    def summary(self) -> str:
        """The line the run prints. Names the block and what answered instead."""
        if self.blocked and self.ok:
            return (f"{', '.join(self.blocked)} blocked - failed over to {self.used}")
        if self.blocked and not self.ok:
            return (f"{', '.join(self.blocked)} blocked and no failover succeeded for "
                    f"{self.item}: " + "; ".join(f"{a.name} {a.state}" for a in self.attempts))
        if self.ok and len(self.attempts) > 1:
            return f"{self.item}: {self.used} (after {len(self.attempts) - 1} failed)"
        if self.ok:
            return f"{self.item}: {self.used}"
        return (f"{self.item}: every source failed - "
                + "; ".join(f"{a.name} {a.state} ({a.detail[:60]})" for a in self.attempts))


def classify(exc: BaseException | None = None, status: int | None = None) -> str:
    """`blocked` or `failed`. A host that ANSWERED a refusal is blocked; silence is a fault."""
    if status is not None and int(status) in BLOCKED_STATUS:
        return "blocked"
    if exc is None:
        return "failed"
    if isinstance(exc, Blocked):
        return "blocked"
    n = type(exc).__name__
    if n in BLOCKED_EXC:
        return "blocked"
    # A requests ConnectionError wrapping a refusal is a block; wrapping a DNS or timeout
    # failure it is a fault. The distinction is in the message, which is all we are given.
    if n == "ConnectionError":
        t = str(exc).lower()
        if "refused" in t or "reset" in t or "forcibly closed" in t:
            return "blocked"
    return "failed"


def chain(item: str, sources: list[Source], ok_if=None) -> Result:
    """Try each source ONCE, in order, and stop at the first success.

    `ok_if` decides whether a returned value counts as a success; the default rejects
    None and an empty container, because an empty answer is not an answer.
    """
    def good(v):
        if ok_if is not None:
            return bool(ok_if(v))
        if v is None:
            return False
        if isinstance(v, (list, tuple, set, dict, str)) and len(v) == 0:
            return False
        if isinstance(v, dict) and v.get("ok") is False:
            return False
        return True

    res = Result(item=item, ok=False)
    for s in sources:
        try:
            v = s.fn()
        except BaseException as e:                             # noqa: BLE001
            state = classify(exc=e)
            res.attempts.append(Attempt(s.name, state, f"{type(e).__name__}: {e}"))
            if state == "blocked":
                res.blocked.append(s.name)
            continue
        # A dict carrying its own status is honoured, so a source can report a 403 it
        # handled itself rather than raising.
        st = v.get("status") if isinstance(v, dict) else None
        if st is not None and classify(status=st) == "blocked":
            res.attempts.append(Attempt(s.name, "blocked", f"HTTP {st}"))
            res.blocked.append(s.name)
            continue
        if good(v):
            res.attempts.append(Attempt(s.name, "ok"))
            res.ok, res.value, res.used = True, v, s.name
            return res
        res.attempts.append(Attempt(s.name, "failed", "empty or rejected value"))
    return res


def self_test() -> int:
    import inspect
    ok = fail = 0

    def chk(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name}  {extra}")

    print("[1] a 403 is a BLOCK, and a timeout is not")
    chk("403 blocks", classify(status=403) == "blocked")
    chk("401 blocks", classify(status=401) == "blocked")
    chk("429 blocks", classify(status=429) == "blocked")
    chk("200 does not", classify(status=200) == "failed")
    chk("500 is a fault, not a block", classify(status=500) == "failed")
    chk("a refused connection blocks",
        classify(exc=ConnectionRefusedError("refused")) == "blocked")
    chk("an explicit Blocked blocks", classify(exc=Blocked("403")) == "blocked")
    chk("a timeout is a fault", classify(exc=TimeoutError("timed out")) == "failed")
    chk("a parse error is a fault", classify(exc=ValueError("bad json")) == "failed")

    print("\n[2] a simulated 403 fails over and SAYS so")
    def nse_403():
        raise Blocked("HTTP 403 from NSE")
    r = chain("live subscription", [Source("NSE", nse_403),
                                    Source("Chittorgarh", lambda: {"total_x": 8.77})])
    chk("the chain succeeds", r.ok is True)
    chk("on the failover source", r.used == "Chittorgarh")
    chk("the value is the failover's", r.value == {"total_x": 8.77})
    chk("the summary names the block and the replacement",
        r.summary == "NSE blocked - failed over to Chittorgarh", r.summary)
    chk("the block is recorded by name", r.blocked == ["NSE"])

    print("\n[3] a 403 returned as a status, not raised")
    r2 = chain("index closes", [Source("niftyindices", lambda: {"status": 403}),
                               Source("BSE", lambda: {"close": 25000.0})])
    chk("still a block", r2.blocked == ["niftyindices"] and r2.ok)
    chk("and the summary says so",
        r2.summary == "niftyindices blocked - failed over to BSE", r2.summary)

    print("\n[4] ONE attempt per host - no retry anywhere")
    calls = []
    def counted():
        calls.append(1)
        raise Blocked("403")
    r3 = chain("x", [Source("NSE", counted), Source("B", lambda: 1)])
    chk("the blocked source was called exactly once", len(calls) == 1, len(calls))
    # Product CODE only. The module docstring explains that a header swap would be a
    # circumvention, so searching the whole source finds the explanation and fails the
    # check it is describing.
    import re as _re
    src = inspect.getsource(sys.modules[__name__]).split("def self_test")[0]
    src = _re.sub(r'(?s)""".*?"""', "", src)
    for label, needle in {"a retry loop": "for _ in range(", "a sleep": "time.sle" + "ep",
                          "a header swap": "User-Ag" + "ent"}.items():
        chk(f"no {label} in the chain", needle not in src, needle)

    print("\n[5] everything blocked is reported as a failure, never as success")
    r4 = chain("live subscription", [Source("NSE", nse_403),
                                     Source("Chittorgarh", nse_403)])
    chk("not ok", r4.ok is False)
    chk("both named", r4.blocked == ["NSE", "Chittorgarh"])
    chk("the summary says no failover succeeded",
        "no failover succeeded" in r4.summary, r4.summary)

    print("\n[6] an empty answer is not an answer")
    r5 = chain("calendar", [Source("NSE", lambda: []), Source("Chittorgarh", lambda: [1])])
    chk("an empty list fails over", r5.ok and r5.used == "Chittorgarh")
    chk("and is a FAULT, not a block", r5.blocked == [])
    r6 = chain("sub", [Source("BSE", lambda: {"ok": False, "why": "no rows"}),
                       Source("NSE", lambda: {"ok": True, "total_x": 1.0})])
    chk("a dict saying ok=False fails over", r6.ok and r6.used == "NSE")

    print(f"\n{ok} passed, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(self_test() if "--self-test" in sys.argv else self_test())
