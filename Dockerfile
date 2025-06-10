# Multi-stage build para otimizar o tamanho da imagem
FROM python:3.11-slim as builder

# Instalar dependências do sistema para builds
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgdal-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (para cache do Docker)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --user -r requirements.txt

# Imagem final
FROM python:3.11-slim

# Instalar dependências do sistema necessárias em runtime
RUN apt-get update && apt-get install -y \
    libgdal-dev \
    libspatialindex-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root para segurança
RUN useradd --create-home --shell /bin/bash delivery

# Copiar dependências instaladas
COPY --from=builder /root/.local /home/delivery/.local

# Configurar PATH para o usuário
ENV PATH=/home/delivery/.local/bin:$PATH

# Criar diretórios necessários
WORKDIR /app
RUN mkdir -p /app/data /app/logs /app/uploads /app/frontend/static /app/frontend/templates && \
    chown -R delivery:delivery /app

# Copiar código da aplicação
COPY --chown=delivery:delivery . .

# Mudar para usuário não-root
USER delivery

# Configurar variáveis de ambiente
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expor porta
EXPOSE 8800

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8800/health || exit 1

# Comando para iniciar a aplicação
CMD ["fastapi", "run", "backend.main:app", "--host", "0.0.0.0", "--port", "8800"]
