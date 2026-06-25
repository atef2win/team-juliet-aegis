FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    tar \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v0.26.68/c2patool-v0.26.68-x86_64-unknown-linux-gnu.tar.gz | tar -xz -C /usr/local/bin/

RUN pip install --no-cache-dir flask requests cryptography base58

COPY app.py .
CMD ["python", "app.py"]
