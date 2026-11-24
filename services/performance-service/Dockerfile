# python:3.12-slim chosen over alpine because:
# - motor (async MongoDB driver) uses C extensions that need glibc
# - slim gives a clean, reproducible layer without manual musl workarounds
# - pika is pure Python but benefits from the same stable base
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY . .

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
