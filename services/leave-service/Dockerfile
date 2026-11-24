# python:3.12-slim chosen over alpine because:
# - psycopg2-binary requires glibc (not available in alpine by default)
# - pika (RabbitMQ client) has no known alpine issues but slim is safer
# - image stays under 200MB; alpine's savings are marginal given the deps
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
