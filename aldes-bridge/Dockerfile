FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir cryptography

COPY server/ ./server/
COPY translations/ ./translations/
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 18883
ENTRYPOINT ["/run.sh"]