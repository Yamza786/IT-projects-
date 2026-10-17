FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENTERPRISE_DB=/data/enterprise.db PORT=10000
WORKDIR /app
COPY devops-demo/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --system --uid 10001 --create-home appuser \
    && mkdir /data && chown appuser:appuser /data
COPY polymath-enterprise/app ./app
USER appuser
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/health', timeout=2)" || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\""]
