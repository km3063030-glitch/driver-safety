from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from services.common import config

TOPICS = {config.TOPIC_RAW: 6, config.TOPIC_DLQ: 1, config.TOPIC_ALERTS: 1}


def main():
    admin = AdminClient({"bootstrap.servers": config.KAFKA_BOOTSTRAP})
    new_topics = [
        NewTopic(name, num_partitions=parts, replication_factor=1)
        for name, parts in TOPICS.items()
    ]
    for name, future in admin.create_topics(new_topics).items():
        try:
            future.result()
            print("created", name)
        except KafkaException as exc:
            print(name, "->", exc)


if __name__ == "__main__":
    main()