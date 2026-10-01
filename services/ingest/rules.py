import bisect


class HarshBurstRule:
    """Fire when `threshold` harsh events fall inside `window_s` for one VIN."""

    def __init__(self, window_s, threshold, cooldown_s):
        self.window_s = window_s
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._times = {}
        self._last_alert = {}

    def observe(self, vin, t):
        """Record a harsh event at time t. Return the count if an alert fires."""
        times = self._times.setdefault(vin, [])
        bisect.insort(times, t)
        newest = times[-1]
        cut = bisect.bisect_left(times, newest - self.window_s)
        if cut:
            del times[:cut]
        if len(times) < self.threshold:
            return None
        if newest - self._last_alert.get(vin, float("-inf")) < self.cooldown_s:
            return None
        self._last_alert[vin] = newest
        return len(times)

    def prune(self, now):
        """Drop state for vehicles that have gone quiet."""
        horizon = now - self.window_s
        for vin in [v for v, times in self._times.items() if times[-1] < horizon]:
            del self._times[vin]
        horizon = now - self.cooldown_s
        for vin in [v for v, t in self._last_alert.items() if t < horizon]:
            del self._last_alert[vin]