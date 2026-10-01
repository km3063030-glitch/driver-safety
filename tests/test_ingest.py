from datetime import datetime, timezone

from services.ingest import main as ingest


class FakeCursor:
    def __init__(self):
        self.rows = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def executemany(self, _sql, rows):
        self.rows = rows


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_write_alerts_publishes_and_persists_rows():
    connection = FakeConnection()

    class Producer:
        def __init__(self):
            self.messages = []

        def produce(self, *args, **kwargs):
            self.messages.append((args, kwargs))

    producer = Producer()
    events = [
        ({"vin": "VIN1", "evt": "HARSH_BRAKE", "ts": "time", "_t": 10,
          "lat": 1.0, "lon": 2.0}, 8),
        ({"vin": "VIN2", "evt": "HARSH_ACCEL", "ts": "time", "_t": 11,
          "lat": 3.0, "lon": 4.0}, 4),
    ]
    ingest.write_alerts(connection, producer, events)
    assert [row[2] for row in connection.cursor_value.rows] == ["HIGH", "MEDIUM"]
    assert all(row[1] == "HARSH_BURST" for row in connection.cursor_value.rows)
    assert len(producer.messages) == 2
    assert connection.commits == 1
    assert connection.cursor_value.rows[0][3] == datetime.fromtimestamp(10, timezone.utc)


def test_ingest_starts_once_flushes_on_shutdown_and_commits_after_flush(monkeypatch):
    actions = []
    handlers = []
    connection = FakeConnection()

    class Consumer:
        def __init__(self, _options):
            self.stopped = False

        def subscribe(self, topics):
            assert topics == [ingest.config.TOPIC_RAW]

        def consume(self, **_kwargs):
            if not self.stopped:
                self.stopped = True
                handlers[0](None, None)
            return []

        def commit(self, **_kwargs):
            actions.append("commit")

        def close(self):
            actions.append("consumer-close")

    class Producer:
        def __init__(self, _options):
            pass

        def flush(self, _timeout):
            actions.append("producer-flush")

        def poll(self, _timeout):
            pass

    class Writer:
        written = 0

        def due(self):
            return False

        def flush(self):
            actions.append("writer-flush")

    monkeypatch.setattr(ingest, "Consumer", Consumer)
    monkeypatch.setattr(ingest, "Producer", Producer)
    monkeypatch.setattr(ingest, "ClickHouseWriter", Writer)
    monkeypatch.setattr(ingest.signal, "signal", lambda _sig, handler: handlers.append(handler))
    monkeypatch.setattr(ingest.redis.Redis, "from_url", lambda _url: object())
    monkeypatch.setattr(ingest.psycopg, "connect", lambda _url: connection)

    ingest.main()
    assert actions.index("writer-flush") < actions.index("commit")
    assert actions == ["writer-flush", "commit", "consumer-close", "producer-flush"]
    assert connection.closed


def test_ingest_writes_fresh_event_then_flushes_before_commit(monkeypatch):
    actions = []
    handlers = []
    connection = FakeConnection()
    event = {
        "vin": "VIN1", "seq": 1, "ts": "2026-10-01T12:00:00Z",
        "lat": 10.0, "lon": 78.0, "speed_kmh": 50.0, "odo_km": 1.0,
        "evt": None, "_t": 1790856000,
    }

    class Message:
        def error(self):
            return None

        def value(self):
            return b"valid-json"

        def key(self):
            return b"VIN1"

    class Consumer:
        def __init__(self, _options):
            self.calls = 0

        def subscribe(self, _topics):
            pass

        def consume(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return [Message()]
            if self.calls == 2:
                handlers[0](None, None)
            return []

        def commit(self, **_kwargs):
            actions.append("commit")

        def close(self):
            actions.append("close")

    class Producer:
        def __init__(self, _options):
            pass

        def flush(self, _timeout):
            actions.append("producer-flush")

        def poll(self, _timeout):
            pass

    class Pipeline:
        def set(self, *_args, **_kwargs):
            pass

        def execute(self):
            return [True]

    class Cache:
        def pipeline(self, **_kwargs):
            return Pipeline()

    class Writer:
        written = 1

        def add(self, received):
            assert received is event
            actions.append("add")

        def due(self):
            return True

        def flush(self):
            actions.append("writer-flush")

    monkeypatch.setattr(ingest, "Consumer", Consumer)
    monkeypatch.setattr(ingest, "Producer", Producer)
    monkeypatch.setattr(ingest, "ClickHouseWriter", Writer)
    monkeypatch.setattr(ingest.signal, "signal", lambda _sig, handler: handlers.append(handler))
    monkeypatch.setattr(ingest.redis.Redis, "from_url", lambda _url: Cache())
    monkeypatch.setattr(ingest.psycopg, "connect", lambda _url: connection)
    monkeypatch.setattr(ingest, "validate", lambda _value: (event, None))

    ingest.main()
    assert actions[:4] == ["add", "writer-flush", "commit", "writer-flush"]
    assert actions.index("writer-flush") < actions.index("commit")
