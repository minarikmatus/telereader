FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# the target Kubernetes namespace enforces non-root (PSA restricted)
USER 1000

CMD ["python", "-u", "/app/main.py"]
