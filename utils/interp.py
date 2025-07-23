import numpy as np
from scipy.interpolate import interp1d


def interp1_zero(x, y, xi):
    """
    Safe interpolation function.
    Returns 0 for values outside the range of x.

    Parameters:
    - x: array-like of known x-values
    - y: array-like of known y-values
    - xi: array-like of x-values to interpolate

    Returns:
    - numpy array of interpolated y-values
    """
    x = np.array(x)
    y = np.array(y)
    xi = np.array(xi)

    # Create interpolator (bounds_error=False avoids crash; fill_value=0 fills outside bounds)
    f = interp1d(x, y, bounds_error=False, fill_value=0.0)

    return f(xi)
