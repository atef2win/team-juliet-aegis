FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask requests psycopg2-binary opentimestamps
COPY app.py .
CMD ["python", "app.py"]
