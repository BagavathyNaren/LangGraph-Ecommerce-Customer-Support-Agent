FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Upgrade pip first to use the faster resolver
RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the spaCy model used by Presidio to avoid runtime OOM/timeouts
RUN python -m spacy download en_core_web_lg

COPY . .

# Force Python to recognize the /app directory for imports
ENV PYTHONPATH=/app

# Use sh -c to allow environment variable expansion for $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]