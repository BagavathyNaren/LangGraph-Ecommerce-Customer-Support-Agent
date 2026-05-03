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

ARG GUARDRAILS_AI_API_KEY
RUN guardrails hub install hub://guardrails/toxic_language \
    --token="${GUARDRAILS_AI_API_KEY}" --quiet && \
    guardrails hub install hub://guardrails/detect_jailbreak \
    --token="${GUARDRAILS_AI_API_KEY}" --quiet

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]