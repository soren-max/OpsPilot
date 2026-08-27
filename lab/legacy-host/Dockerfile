FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-server \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash opspilot \
    && mkdir -p /run/sshd /opt/opspilot-demo /var/lib/opspilot-demo \
    && chown -R opspilot:opspilot /var/lib/opspilot-demo

COPY services.sh /opt/opspilot-demo/services.sh
COPY legacy_server.py /opt/opspilot-demo/legacy_server.py
COPY entrypoint.sh /usr/local/bin/legacy-entrypoint
RUN chmod 0755 /opt/opspilot-demo/services.sh /usr/local/bin/legacy-entrypoint

EXPOSE 22 8080
ENTRYPOINT ["/usr/local/bin/legacy-entrypoint"]
