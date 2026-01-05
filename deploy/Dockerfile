FROM python:3.11-slim

WORKDIR /app

# System deps (optional: build essentials for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1

# Dashboard port (internal)
EXPOSE 8888

# Default: dry-run dashboard bound to 0.0.0.0 inside container (put behind reverse proxy!)
CMD ["python", "run_with_dashboard.py", "--dry-run", "--port", "8888", "--bind", "0.0.0.0"]
