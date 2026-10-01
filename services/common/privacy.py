"""Privacy transforms for data leaving backend storage."""

import math


def mask_location(details):
    """Coarsen alert coordinates to roughly kilometer precision for API output."""
    if not isinstance(details, dict):
        return details
    masked = details.copy()
    for coordinate in ("lat", "lon"):
        value = masked.get(coordinate)
        if isinstance(value, (int, float)) and math.isfinite(value):
            masked[coordinate] = round(value, 2)
    return masked
