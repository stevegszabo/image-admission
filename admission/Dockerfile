FROM ubuntu:22.04

USER root
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y curl wget python3 python3-pip python3.10-venv iproute2 lsof netcat-openbsd && \
    apt-get clean

COPY app /app
RUN usermod -d /app www-data
RUN chown -R www-data:www-data /app

USER www-data
RUN python3 -m venv /app/virtual && \
    . /app/virtual/bin/activate && \
    python3 -m pip install -r /app/requirements.txt

EXPOSE 8443
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
