import os
import json
import pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def publish_leave_approved(employee_id: str, leave_id: str, days: int, leave_type: str):
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue="leave_approved", durable=True)
        message = json.dumps({
            "employee_id": employee_id,
            "leave_id": leave_id,
            "days": days,
            "leave_type": leave_type
        })
        channel.basic_publish(
            exchange="",
            routing_key="leave_approved",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f"[Publisher] Published leave_approved for employee {employee_id}")
    except Exception as e:
        print(f"[Publisher] Failed to publish: {e}")
