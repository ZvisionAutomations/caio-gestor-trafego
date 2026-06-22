# Caio — Gestor de Tráfego (Meta Ads) — imagem do agente (story-062)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Dependências primeiro (cache de layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código do agente + configuração (credenciais NÃO entram na imagem — vêm via env_file)
COPY agent/ ./agent/
COPY config/settings.yaml ./config/settings.yaml

# O agente roda scheduler 24/7 + inbound HTTP opcional:
#   08:00 análise · 14:00 check · 20:30 relatório · recalibração D+7 · inbox poll (15min)
#   inbound Evolution: http://caio-trafego:8010/inbound
CMD ["python", "-m", "agent.main"]
