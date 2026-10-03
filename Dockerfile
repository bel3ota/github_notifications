FROM python:3.12-alpine
WORKDIR /app
COPY notifier.py .
RUN mkdir /data && chown 1000:1000 /data
USER 1000
ENV STATE_FILE=/data/state.json PYTHONUNBUFFERED=1
VOLUME /data
CMD ["python", "notifier.py"]
