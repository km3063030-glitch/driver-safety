import time
from datetime import datetime, timezone

import clickhouse_connect

from services.common import config

COLS = ["vin", "seq", "ts", "lat", "lon", "speed_kmh", "odo_km", "evt"]


def _ts(value):
    if isinstance(value, datetime):
        return value
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class ClickHouseWriter:
    def __init__(
        self,
        host="localhost",
        port=8123,
        max_rows=5000,
        max_age_s=1.0,
    ):
        self.client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=config.CLICKHOUSE_USER,
            password=config.CLICKHOUSE_PASSWORD,
        )
        self.max_rows, self.max_age_s = max_rows, max_age_s
        self.buf, self.last_flush = [], time.monotonic()
        self.written = 0

    def add(self, e: dict):
        self.buf.append([
            e["vin"], int(e["seq"]), _ts(e["ts"]),
            float(e["lat"]), float(e["lon"]),
            float(e["speed_kmh"]), float(e["odo_km"]),
            e.get("evt") or "",
        ])

    def due(self) -> bool:
        return len(self.buf) >= self.max_rows or (
            bool(self.buf) and time.monotonic() - self.last_flush >= self.max_age_s)

    def flush(self):
        if not self.buf:
            return
        self.client.insert("telemetry.events", self.buf, column_names=COLS)
        self.written += len(self.buf)
        self.buf.clear()
        self.last_flush = time.monotonic()