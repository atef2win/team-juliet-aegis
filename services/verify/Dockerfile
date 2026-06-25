FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask psycopg2-binary "qrcode[pil]"
COPY app.py .
CMD ["python", "app.py"]
