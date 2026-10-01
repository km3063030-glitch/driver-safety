from types import SimpleNamespace

import pytest

from services.ingest import dlq_sink


class Message:
    def error(self):
        return None

    def topic(self):
        return "telemetry.dlq"

    def partition(self):
        return 2

    def offset(self):
        return 17

    def value(self):
        return b"{invalid-json"


def configure_sink(monkeypatch, collection, actions):
    class FakeConsumer:
        def __init__(self, options):
            assert options["enable.auto.commit"] is False
            self.polls = 0

        def subscribe(self, topics):
            assert topics == [dlq_sink.config.TOPIC_DLQ]

        def poll(self, _timeout):
            self.polls += 1
            if self.polls == 1:
                return Message()
            raise KeyboardInterrupt

        def commit(self, **kwargs):
            actions.append(("commit", kwargs["message"].offset()))

        def close(self):
            actions.append(("consumer-close",))

    mongo = SimpleNamespace(
        driversafety=SimpleNamespace(rejected_events=collection),
        close=lambda: actions.append(("mongo-close",)),
    )
    monkeypatch.setattr(dlq_sink, "Consumer", FakeConsumer)
    monkeypatch.setattr(dlq_sink, "MongoClient", lambda _url: mongo)


def test_dlq_sink_upserts_by_topic_partition_offset_then_commits(monkeypatch):
    actions = []

    class Collection:
        def replace_one(self, selector, document, upsert):
            actions.append(("upsert", selector, document, upsert))

    configure_sink(monkeypatch, Collection(), actions)
    with pytest.raises(KeyboardInterrupt):
        dlq_sink.main()
    assert actions[0][0] == "upsert"
    assert actions[0][1] == {"_id": "telemetry.dlq:2:17"}
    assert actions[0][2]["raw"] == "{invalid-json"
    assert actions[1] == ("commit", 17)
    assert actions[-2:] == [("consumer-close",), ("mongo-close",)]


def test_dlq_sink_does_not_commit_when_mongo_write_fails(monkeypatch):
    actions = []

    class BrokenCollection:
        def replace_one(self, *_args, **_kwargs):
            raise RuntimeError("Mongo unavailable")

    configure_sink(monkeypatch, BrokenCollection(), actions)
    with pytest.raises(RuntimeError, match="Mongo unavailable"):
        dlq_sink.main()
    assert not any(action[0] == "commit" for action in actions)
    assert actions[-2:] == [("consumer-close",), ("mongo-close",)]
