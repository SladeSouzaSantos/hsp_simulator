# Imagem base leve para ARM64 (Raspberry Pi)
FROM python:3.10-slim

WORKDIR /app

# Instala dependências básicas de compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expõe as portas da API (8000) e do Dashboard (8501)
EXPOSE 8000
EXPOSE 8501