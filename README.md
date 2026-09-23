# Laya Ticket Router

Base do microserviço de classificação e routing de tickets internos.

## Trabalho com agentes

As regras operacionais do projeto estão em [AGENTS.md](AGENTS.md). Os
procedimentos, conhecimento, templates e registos reutilizáveis estão em
[AgentDATA/](AgentDATA/README.md).

## Milestone 1

Esta versão fornece apenas a estrutura Flask/Docker e os endpoints de
observabilidade:

- `GET /health`: confirma que o processo HTTP está vivo;
- `GET /ready`: devolve `503` até o modelo ser carregado.

O Laya e o endpoint de classificação serão integrados nos milestones seguintes.

## Executar localmente

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Para iniciar o servidor localmente depois de instalar as dependências:

```bash
.venv/bin/gunicorn \
  --bind 0.0.0.0:8080 \
  --workers 1 \
  --threads 1 \
  --timeout 120 \
  'app.api:create_app()'
```

## Executar com Docker Compose

```bash
docker compose up --build
```

Verificações:

```bash
curl http://localhost:8080/health
curl -i http://localhost:8080/ready
```
