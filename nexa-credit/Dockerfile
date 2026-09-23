# NEXA CREDIT : image unique (interface compilée + serveur). Compatible amd64 et arm64.
FROM node:22-alpine AS front
WORKDIR /f
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NEXA_ENV=prod NEXA_DATA_DIR=/data
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=front /f/dist /app/frontend/dist
RUN mkdir -p /data && chmod 777 /data
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/sante')"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=${NEXA_FORWARDED_ALLOW_IPS:-127.0.0.1}"]
