import math
from datetime import datetime, timezone

CITIES = [
    (12.90, 13.20, 80.10, 80.30),
    (12.85, 13.10, 77.45, 77.75),
    (18.90, 19.25, 72.80, 72.98),
]
RATES_PER_100KM = {
    "HARSH_BRAKE": 3.0,
    "HARSH_ACCEL": 2.0,
    "HARSH_CORNER": 2.0,
    "OVERSPEED": 4.0,
}


def iso(ts):
    moment = datetime.fromtimestamp(ts, timezone.utc)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Vehicle:
    __slots__ = (
        "vin", "mult", "bbox", "lat", "lon", "hdg", "speed", "target",
        "target_until", "odo", "seq", "end_t", "idle",
    )

    def __init__(self, vin, mult, bbox, lat, lon, hdg, odo, seq):
        self.vin = vin
        self.mult = mult
        self.bbox = bbox
        self.lat = lat
        self.lon = lon
        self.hdg = hdg
        self.odo = odo
        self.seq = seq
        self.speed = 0.0
        self.target = 0.0
        self.target_until = 0.0
        self.end_t = 0.0
        self.idle = True


class Fleet:
    def __init__(self, vehicles, active_fraction, boost, rng, seq0):
        self.rng = rng
        self.boost = boost
        self.target_active = round(active_fraction * len(vehicles))
        self.active = []
        self.parked = []
        for i, (vin, risk) in enumerate(vehicles):
            bbox = CITIES[i % len(CITIES)]
            self.parked.append(
                Vehicle(
                    vin=vin,
                    mult=0.4 + 8.0 * risk,
                    bbox=bbox,
                    lat=rng.uniform(bbox[0], bbox[1]),
                    lon=rng.uniform(bbox[2], bbox[3]),
                    hdg=rng.uniform(0, 2 * math.pi),
                    odo=rng.uniform(5000, 80000),
                    seq=seq0,
                )
            )

    def step(self, now, dt):
        out = []
        deficit = self.target_active - len(self.active)
        if deficit > 0 and self.parked:
            for _ in range(min(len(self.parked), max(1, deficit // 10))):
                index = self.rng.randrange(len(self.parked))
                self.parked[index], self.parked[-1] = self.parked[-1], self.parked[index]
                vehicle = self.parked.pop()
                out.append(self._begin(vehicle, now))
                self.active.append(vehicle)
        still_driving = []
        for vehicle in self.active:
            if now >= vehicle.end_t:
                vehicle.speed = 0.0
                out.append(self._event(vehicle, now, "IGNITION_OFF"))
                self.parked.append(vehicle)
            else:
                out.append(self._drive(vehicle, now, dt))
                still_driving.append(vehicle)
        self.active = still_driving
        return out

    def _begin(self, v, now):
        v.end_t = now + self.rng.uniform(300, 1800)
        v.speed = 0.0
        v.target = 0.0
        v.target_until = 0.0
        v.idle = True
        return self._event(v, now, "IGNITION_ON")

    def _drive(self, v, now, dt):
        rng = self.rng
        if now >= v.target_until:
            roll = rng.random()
            if roll < 0.08:
                v.target = 0.0
            elif roll < 0.6:
                v.target = rng.uniform(15, 60)
            else:
                v.target = rng.uniform(50, 85)
            v.target_until = now + rng.uniform(15, 60)
        v.speed += max(-8.0 * dt, min(5.0 * dt, v.target - v.speed))
        km = v.speed * dt / 3600.0
        v.odo += km
        v.hdg += rng.gauss(0, 0.05)
        v.lat += km * math.cos(v.hdg) / 111.0
        v.lon += km * math.sin(v.hdg) / (111.0 * math.cos(math.radians(v.lat)))
        south, north, west, east = v.bbox
        if not (south <= v.lat <= north and west <= v.lon <= east):
            v.hdg += math.pi
            v.lat = min(max(v.lat, south), north)
            v.lon = min(max(v.lon, west), east)
        evt = self._roll_event(v, km)
        if evt is None:
            if v.speed < 0.5 and not v.idle:
                v.idle = True
                evt = "IDLE_START"
            elif v.speed >= 1.0:
                v.idle = False
        return self._event(v, now, evt)

    def _roll_event(self, v, km):
        scale = v.mult * self.boost * km / 100.0
        roll = self.rng.random()
        cumulative = 0.0
        for name, rate in RATES_PER_100KM.items():
            cumulative += rate * scale
            if roll < cumulative:
                self._apply(v, name)
                return name
        return None

    def _apply(self, v, name):
        if name == "HARSH_BRAKE":
            v.speed = max(0.0, v.speed - self.rng.uniform(15, 30))
        elif name == "HARSH_ACCEL":
            v.speed += self.rng.uniform(10, 20)
        elif name == "OVERSPEED":
            v.speed = max(v.speed, self.rng.uniform(85, 110))

    def _event(self, v, now, evt):
        v.seq += 1
        return {
            "vin": v.vin,
            "ts": iso(now),
            "lat": round(v.lat, 5),
            "lon": round(v.lon, 5),
            "speed_kmh": round(v.speed, 1),
            "odo_km": round(v.odo, 1),
            "evt": evt,
            "seq": v.seq,
        }