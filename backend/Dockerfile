FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN useradd --create-home --uid 10001 wbinsight

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY VERSION /app/VERSION
COPY backend/ /app/backend/

RUN mkdir -p /app/backend/static /app/backend/uploads \
    && chown -R wbinsight:wbinsight /app

USER wbinsight

EXPOSE 9000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers", "--forwarded-allow-ips=*"]
