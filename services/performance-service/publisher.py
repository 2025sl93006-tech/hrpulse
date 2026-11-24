import os
import json
import pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def publish_performance_rated(employee_id: str, review_id: str, rating: int):
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue="performance_rated", durable=True)
        message = json.dumps({
            "employee_id": employee_id,
            "review_id": review_id,
            "rating": rating
        })
        channel.basic_publish(
            exchange="",
            routing_key="performance_rated",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f"[Publisher] Published performance_rated for employee {employee_id}")
    except Exception as e:
        print(f"[Publisher] Failed to publish: {e}")
