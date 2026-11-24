import os
import json
import threading
import pika
from sqlalchemy.orm import Session
from database import SessionLocal
from models import PayrollAdjustment, AdjustmentType

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def handle_leave_approved(ch, method, properties, body):
    data = json.loads(body)
    employee_id = data["employee_id"]
    days = data["days"]
    leave_type = data["leave_type"]
    db: Session = SessionLocal()
    try:
        # Deduct only unpaid leave types (sick/casual beyond entitlement are free here;
        # for demo, we deduct a fixed daily rate of 1000 for leave_without_pay)
        if leave_type == "annual":
            amount = 0.0  # paid leave — no deduction
        else:
            amount = days * 1000.0  # demo rate

        print(f"[Consumer] Leave deduction recorded: {employee_id}, {leave_type}, days={days}, amount={amount}")
        if amount > 0:
            adj = PayrollAdjustment(
                employee_id=employee_id,
                adjustment_type=AdjustmentType.leave_deduction,
                amount=amount,
                description=f"{leave_type} leave: {days} days"
            )
            db.add(adj)
            db.commit()
            print(f"[Consumer] Leave deduction recorded: {employee_id} -> -{amount}")
    finally:
        db.close()
    ch.basic_ack(delivery_tag=method.delivery_tag)

def handle_performance_rated(ch, method, properties, body):
    data = json.loads(body)
    employee_id = data["employee_id"]
    rating = data["rating"]
    db: Session = SessionLocal()
    try:
        # Bonus: rating 5 = 20000, rating 4 = 10000, rating 3 = 5000
        bonus_map = {5: 20000.0, 4: 10000.0, 3: 5000.0, 2: 0.0, 1: 0.0}
        bonus = bonus_map.get(rating, 0.0)
        if bonus > 0:
            adj = PayrollAdjustment(
                employee_id=employee_id,
                adjustment_type=AdjustmentType.performance_bonus,
                amount=bonus,
                description=f"Performance bonus for rating {rating}/5"
            )
            db.add(adj)
            db.commit()
            print(f"[Consumer] Performance bonus recorded: {employee_id} -> +{bonus}")
    finally:
        db.close()
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consumer():
    import time
    # Retry until RabbitMQ is ready
    for attempt in range(10):
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue="leave_approved", durable=True)
            channel.queue_declare(queue="performance_rated", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="leave_approved", on_message_callback=handle_leave_approved)
            channel.basic_consume(queue="performance_rated", on_message_callback=handle_performance_rated)
            print("[Consumer] Waiting for messages...")
            channel.start_consuming()
            break
        except Exception as e:
            print(f"[Consumer] Connection failed (attempt {attempt+1}/10): {e}")
            time.sleep(5)

def start_consumer_thread():
    t = threading.Thread(target=start_consumer, daemon=True)
    t.start()
