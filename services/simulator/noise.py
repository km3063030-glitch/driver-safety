import heapq
import json


class Noise:
    def __init__(self, rng, dup=0.03, late=0.02, bad=0.005, late_max=30.0):
        self.rng = rng
        self.dup = dup
        self.late = late
        self.bad = bad
        self.late_max = late_max
        self._heap = []
        self._n = 0

    def process(self, now, event):
        """Return the (key, payload) pairs to publish right now."""
        vin = event["vin"]
        payload = json.dumps(event, separators=(",", ":")).encode()
        if self.rng.random() < self.bad:
            return [(vin, self._corrupt(event, payload))]
        if self.rng.random() < self.late:
            self._n += 1
            due = now + self.rng.uniform(5.0, self.late_max)
            heapq.heappush(self._heap, (due, self._n, vin, payload))
            return []
        out = [(vin, payload)]
        if self.rng.random() < self.dup:
            out.append((vin, payload))
        return out

    def release_due(self, now):
        out = []
        while self._heap and self._heap[0][0] <= now:
            _, _, vin, payload = heapq.heappop(self._heap)
            out.append((vin, payload))
        return out

    def _corrupt(self, event, payload):
        if self.rng.random() < 0.5:
            return payload[: len(payload) // 2]
        vin = event["vin"]
        swapped = "0" if vin[8] != "0" else "1"
        broken = dict(event, vin=vin[:8] + swapped + vin[9:])
        return json.dumps(broken, separators=(",", ":")).encode()