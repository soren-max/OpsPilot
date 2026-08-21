FROM python:3.13-alpine

WORKDIR /opt/lab
COPY demo_service.py ./demo_service.py
USER 65534:65534
EXPOSE 8080 8081
ENTRYPOINT ["python", "/opt/lab/demo_service.py"]
