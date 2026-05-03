FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG GUARDRAILS_AI_API_KEY
RUN echo "enable_metrics=false" > ~/.guardrailsrc && \
    echo "enable_remote_inferencing=false" >> ~/.guardrailsrc && \
    echo "token=${GUARDRAILS_AI_API_KEY}" >> ~/.guardrailsrc && \
    guardrails hub install hub://guardrails/toxic_language --quiet && \
    guardrails hub install hub://guardrails/detect_jailbreak --quiet

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]