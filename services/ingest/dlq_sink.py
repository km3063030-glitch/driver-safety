from confluent_kafka import Consumer
from pymongo import MongoClient

from services.common import config


def main():
    mongo = MongoClient(config.MONGO_URL)
    collection = mongo.driversafety.rejected_events
    consumer = Consumer({
        "bootstrap.servers": config.KAFKA_BOOTSTRAP,
        "group.id": "dlq-sink",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([config.TOPIC_DLQ])
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None or message.error():
                continue
            document = {
                "_id": f"{message.topic()}:{message.partition()}:{message.offset()}",
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
                "raw": message.value().decode(errors="replace"),
            }
            collection.replace_one({"_id": document["_id"]}, document, upsert=True)
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()
        mongo.close()


if __name__ == "__main__":
    main()