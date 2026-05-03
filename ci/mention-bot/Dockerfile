FROM python:3.13-alpine

WORKDIR /app
COPY webhook_responder.py /app/webhook_responder.py

EXPOSE 8095
CMD ["python", "/app/webhook_responder.py"]
