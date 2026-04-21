import numpy as np


def interp_vector(xp, fp, x):
    """Robust 1D interpolation (with left/right clamp)."""
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)
    x = np.asarray(x, dtype=float)

    # sort lists in case x list was not sorted, which the function needs
    sort_inds = xp.argsort()
    fp = fp[sort_inds]  # sort y list based on x list
    xp = np.sort(xp)

    return np.interp(x, xp, fp, left=fp[0], right=fp[-1])


def multi_interp_vector(xp, fp, x):
    """1D interpolation where fp is a 2D array corresponding to each element in x."""
    xp = np.asarray(xp, dtype=float)
    fp = np.asarray(fp, dtype=float)  # each element of fp must be the same length as xp
    x = np.asarray(x, dtype=float)  # the number of elements in fp must be the same as in x

    sort_inds = xp.argsort()
    fp = fp[:, sort_inds]
    xp = np.sort(xp)

    interp = np.empty_like(x, dtype=fp.dtype)

    left = x <= xp[0]
    interp[left] = fp[left, 0]  # set values where x <= xp[0] equal to fp[0]

    right = x >= xp[-1]
    interp[right] = fp[right, -1]  # set values where x >= xp[-1] equal to fp[-1]

    empty = np.isnan(x)
    interp[empty] = np.nan  # set values where x = nan to nan

    mid = np.invert(left + right + empty)
    if np.any(mid):
        x_mid = x[mid]
        i = np.where(mid)[0]
        j = np.searchsorted(xp, x_mid) - 1

        d = (x_mid - xp[j]) / (xp[j + 1] - xp[j])
        interp[mid] = (1 - d) * fp[i, j] + d * fp[i, j + 1]

    return interp
