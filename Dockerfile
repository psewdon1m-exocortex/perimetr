FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG PERIMETR_INSTALL_DEV_DEPENDENCIES=false
COPY requirements.runtime.txt requirements.dev.txt ./
RUN pip install --no-cache-dir -r requirements.runtime.txt \
    && if [ "$PERIMETR_INSTALL_DEV_DEPENDENCIES" = "true" ]; then \
         pip install --no-cache-dir -r requirements.dev.txt; \
       fi

RUN groupadd --gid 10001 perimetr \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin perimetr \
    && mkdir -p /app/.tmp /opt/perimetr/pod-runtime \
    && chown -R perimetr:perimetr /app /opt/perimetr

COPY --chown=perimetr:perimetr alembic.ini ./
COPY --chown=perimetr:perimetr migrations ./migrations
COPY --chown=perimetr:perimetr app ./app
COPY --chown=perimetr:perimetr pod-runtime /opt/perimetr/pod-runtime

USER perimetr

EXPOSE 18080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PERIMETR_LISTEN_PORT','18080')+'/v1/health',timeout=3).read()"

CMD ["sh", "-c", "exec uvicorn app.api_service.app:create_app --factory --host 0.0.0.0 --port ${PERIMETR_LISTEN_PORT:-18080} --proxy-headers --forwarded-allow-ips='*'"]
