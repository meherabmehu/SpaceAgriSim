FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && useradd --create-home --uid 10001 spaceagri \
    && mkdir -p /app/.spaceagrisim \
    && chown spaceagri:spaceagri /app/.spaceagrisim
COPY --chown=spaceagri:spaceagri backend/app /app/backend/app
COPY --chown=spaceagri:spaceagri data /app/data
COPY --chown=spaceagri:spaceagri ml /app/ml
USER spaceagri
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/api/health', timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-graceful-shutdown 25"]
