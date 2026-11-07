FROM python:3.12-slim
ARG BUILD_REVISION=local
ENV BUILD_REVISION=$BUILD_REVISION PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --chown=10001:10001 app/ ./
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2)"]
CMD ["python","server.py"]
