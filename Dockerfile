FROM python:3.10.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Pilot-only: includes credentials in the image.
# All users with image access can extract this file.
COPY .env /srv/.env

RUN useradd --create-home appuser \
    && chmod 600 /srv/.env \
    && chown appuser:appuser /srv/.env

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
