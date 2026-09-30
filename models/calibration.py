"""
models/calibration.py — probability calibrators in pure numpy.

scikit-learn is unavailable (PLAN.md rule 10 and Windows Application Control), so both
calibrators are implemented here and unit-checked in stage3_calibration.py.

  * `IsotonicCalibrator` — pool-adjacent-violators (PAV), the exact solution to the
    L2-isotonic problem. Non-parametric and monotone, so it can fix an arbitrary
    reliability curve, but it can overfit a small fold and it cannot extrapolate.
  * `PlattCalibrator` — a two-parameter logistic fitted on logit(p): p' = sigmoid(a·z + b).
    Rigid, but stable on few rows.

Both are fitted **out of time**: for test year T the calibrator sees only out-of-fold
predictions from years before T. A calibrator fitted on the rows it then corrects would
report a flatteringly good Brier score.
"""
from __future__ import annotations
import numpy as np

EPS = 1e-6


def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def brier(y, p) -> float:
    """Mean squared error of a probability forecast. Lower is better."""
    y = np.asarray(y, float); p = np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def pav(y: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """Pool-adjacent-violators: the non-decreasing sequence minimising weighted squared
    error against y. Returns fitted values in the same order as y."""
    y = np.asarray(y, float)
    w = np.ones_like(y) if w is None else np.asarray(w, float)
    # blocks of (weighted sum, total weight, element count); merge backwards whenever the
    # previous block's mean exceeds the current one's, which is the PAV step
    sums, wts, cnts = [], [], []
    for yi, wi in zip(y, w):
        sums.append(yi * wi); wts.append(wi); cnts.append(1)
        while len(sums) > 1 and sums[-2] / wts[-2] > sums[-1] / wts[-1] + 1e-15:
            s, t, c = sums.pop(), wts.pop(), cnts.pop()
            sums[-1] += s; wts[-1] += t; cnts[-1] += c
    out, idx = np.empty_like(y), 0
    for s, t, c in zip(sums, wts, cnts):
        out[idx:idx + c] = s / t
        idx += c
    return out


class IsotonicCalibrator:
    """Monotone non-parametric calibration by PAV, applied by linear interpolation."""

    name = "isotonic"

    def fit(self, p, y):
        p = np.asarray(p, float); y = np.asarray(y, float)
        order = np.argsort(p, kind="mergesort")
        xs, ys = p[order], y[order]
        fitted = pav(ys)
        # collapse duplicate x by averaging their fitted values, so interp is well defined
        uniq, inv = np.unique(xs, return_inverse=True)
        agg = np.zeros(len(uniq)); cnt = np.zeros(len(uniq))
        np.add.at(agg, inv, fitted); np.add.at(cnt, inv, 1.0)
        self.x_, self.y_ = uniq, agg / cnt
        return self

    def predict(self, p):
        return np.clip(np.interp(np.asarray(p, float), self.x_, self.y_), 0.0, 1.0)


class PlattCalibrator:
    """p' = sigmoid(a * logit(p) + b), fitted by Newton's method on log-loss."""

    name = "platt"

    def fit(self, p, y, tol=1e-10, max_iter=200):
        z = _logit(p); y = np.asarray(y, float)
        X = np.column_stack([z, np.ones_like(z)])
        b = np.zeros(2)
        for _ in range(max_iter):
            q = 1 / (1 + np.exp(-X @ b))
            g = X.T @ (q - y)
            W = q * (1 - q) + 1e-12
            H = (X * W[:, None]).T @ X
            step = np.linalg.solve(H, g)
            b -= step
            if np.abs(step).max() < tol:
                break
        self.a_, self.b_ = float(b[0]), float(b[1])
        return self

    def predict(self, p):
        return 1 / (1 + np.exp(-(self.a_ * _logit(p) + self.b_)))


class RawCalibrator:
    """Identity — the uncalibrated baseline."""

    name = "raw"

    def fit(self, p, y):
        return self

    def predict(self, p):
        return np.asarray(p, float)


CALIBRATORS = (RawCalibrator, PlattCalibrator, IsotonicCalibrator)


def reliability(y, p, bins: int = 10):
    """Decile reliability table: n, mean predicted, actual rate, gap."""
    import pandas as pd
    edges = np.linspace(0, 1, bins + 1)
    b = pd.cut(pd.Series(np.asarray(p, float)), edges, include_lowest=True)
    t = (pd.DataFrame({"y": np.asarray(y, float), "p": np.asarray(p, float), "bin": b})
         .groupby("bin", observed=False)
         .agg(n=("y", "size"), mean_pred=("p", "mean"), actual=("y", "mean")).reset_index())
    t["gap"] = t["actual"] - t["mean_pred"]
    t["bin"] = t["bin"].astype(str)
    return t
