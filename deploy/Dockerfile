FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY ralleh_voice ./ralleh_voice
COPY static ./static

RUN pip install --no-cache-dir .

EXPOSE 8099
CMD ["uvicorn", "ralleh_voice.app:app", "--host", "0.0.0.0", "--port", "8099"]
