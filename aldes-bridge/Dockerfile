FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables \
    python3-cryptography \
    && rm -rf /var/lib/apt/lists/*

COPY server/ ./server/
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 18883
ENTRYPOINT ["/run.sh"]