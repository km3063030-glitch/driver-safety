from datetime import datetime, timezone

import pytest

from services.common import ch_writer


def test_writer_adds_normalized_rows_and_flushes(monkeypatch):
    inserted = []

    class FakeClient:
        def insert(self, table, rows, column_names):
            inserted.append((table, [row.copy() for row in rows], column_names))

    monkeypatch.setattr(ch_writer.clickhouse_connect, "get_client", lambda **_kwargs: FakeClient())
    writer = ch_writer.ClickHouseWriter(max_rows=2, max_age_s=100)
    writer.add({
        "vin": "VIN1", "seq": "3", "ts": "2026-10-01T12:00:00Z",
        "lat": "10.1", "lon": "78.2", "speed_kmh": "44.5", "odo_km": "123.4",
    })
    writer.add({
        "vin": "VIN2", "seq": 4, "ts": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "lat": 10, "lon": 78, "speed_kmh": 0, "odo_km": 1, "evt": "HARSH_BRAKE",
    })
    assert writer.due()
    writer.flush()
    assert writer.written == 2
    assert writer.buf == []
    assert inserted[0][0] == "telemetry.events"
    assert inserted[0][1][0][1] == 3
    assert inserted[0][1][0][2] == datetime(2026, 10, 1, 12, tzinfo=timezone.utc).replace(tzinfo=None)
    assert inserted[0][1][0][-1] == ""
    assert inserted[0][2] == ch_writer.COLS


def test_writer_keeps_batch_if_insert_fails(monkeypatch):
    class BrokenClient:
        def insert(self, *_args, **_kwargs):
            raise RuntimeError("insert failed")

    monkeypatch.setattr(ch_writer.clickhouse_connect, "get_client", lambda **_kwargs: BrokenClient())
    writer = ch_writer.ClickHouseWriter()
    event = {
        "vin": "VIN1", "seq": 1, "ts": "2026-10-01T12:00:00Z",
        "lat": 10, "lon": 78, "speed_kmh": 0, "odo_km": 1,
    }
    writer.add(event)
    with pytest.raises(RuntimeError, match="insert failed"):
        writer.flush()
    assert len(writer.buf) == 1
    assert writer.written == 0


def test_writer_empty_batch_is_not_due_or_inserted(monkeypatch):
    class FakeClient:
        def insert(self, *_args, **_kwargs):
            raise AssertionError("empty batch must not insert")

    monkeypatch.setattr(ch_writer.clickhouse_connect, "get_client", lambda **_kwargs: FakeClient())
    writer = ch_writer.ClickHouseWriter()
    assert not writer.due()
    writer.flush()
    assert writer.written == 0
