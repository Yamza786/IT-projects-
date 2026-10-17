FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8090 LAB_DB=/data/lab.db
WORKDIR /app
COPY app.py .
RUN useradd --system --uid 10001 app && mkdir /data && chown app:app /data
USER 10001
EXPOSE 8090
HEALTHCHECK --interval=20s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=2)" || exit 1
CMD ["python","app.py"]
