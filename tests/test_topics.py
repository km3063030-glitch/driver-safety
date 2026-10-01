from services.common import topics


def test_topic_initializer_creates_configured_topics(monkeypatch, capsys):
    created = []

    class Future:
        def result(self):
            return None

    class Admin:
        def __init__(self, config):
            assert config["bootstrap.servers"] == topics.config.KAFKA_BOOTSTRAP

        def create_topics(self, definitions):
            created.extend(definitions)
            return {definition.topic: Future() for definition in definitions}

    monkeypatch.setattr(topics, "AdminClient", Admin)
    topics.main()
    assert {topic.topic: topic.num_partitions for topic in created} == topics.TOPICS
    assert "created" in capsys.readouterr().out
