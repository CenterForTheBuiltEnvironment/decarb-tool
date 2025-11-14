import numpy as np


def interp_vector(xp, fp, x):
    """Robust 1D interpolation (with left/right clamp)."""
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)
    x = np.asarray(x, dtype=float)

    # sort lists in case x list was not sorted, which the function needs
    sort_inds = xp.argsort()
    fp = fp[sort_inds] # sort y list based on x list
    xp = np.sort(xp)

    return np.interp(x, xp, fp, left=fp[0], right=fp[-1])
