# python:3.12-slim chosen over alpine because:
# - pybreaker and psycopg2-binary both require glibc, making alpine impractical
# - slim + no-cache pip install keeps the final image ~190MB
# - reload=False in production CMD because the consumer thread must not restart mid-message
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
