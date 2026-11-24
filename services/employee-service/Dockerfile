# python:3.12-slim chosen over alpine because:
# - psycopg2-binary requires glibc (not available in alpine by default)
# - slim keeps image under 200MB while alpine would need manual build deps
# - better pip compatibility for all packages without custom compile steps
FROM python:3.12-slim

WORKDIR /app

# Install OS-level deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
