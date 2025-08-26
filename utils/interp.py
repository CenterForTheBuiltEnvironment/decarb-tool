import numpy as np


def interp_vector(xp, fp, x):
    """Robust 1D interpolation (with left/right clamp)."""
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)
    x = np.asarray(x, dtype=float)
    return np.interp(x, xp, fp, left=fp[0], right=fp[-1])
