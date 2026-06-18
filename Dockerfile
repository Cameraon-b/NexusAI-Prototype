FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEXUSAI_DB_PATH=/data/nexusai.db

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" python-multipart

COPY app ./app
RUN mkdir -p /data

EXPOSE 5055

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5055"]
