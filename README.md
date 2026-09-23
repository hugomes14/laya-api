# Laya Ticket Router

Base do microserviço de classificação e routing de tickets internos.

## Trabalho com agentes

As regras operacionais do projeto estão em [AGENTS.md](AGENTS.md). Os
procedimentos, conhecimento, templates e registos reutilizáveis estão em
[AgentDATA/](AgentDATA/README.md).

## Milestones 1 e 2

O serviço disponibiliza:

- `GET /health`: confirma que o processo HTTP está vivo;
- `GET /ready`: devolve `200` apenas depois do modelo estar carregado;
- `POST /v1/classify-only`: classifica a categoria sem escolher o destino.

O endpoint recebe `ticket_id` (opcional), `subject` e `body` (opcional), e
devolve categoria, confiança, probabilidades, versão do modelo e latência. O
carregamento do checkpoint multilingual acontece uma vez no arranque. A primeira
execução precisa de acesso ao Hugging Face, salvo se o checkpoint já estiver em
cache.

Exemplo:

```bash
curl -X POST http://localhost:8080/v1/classify-only \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"INC-12345","subject":"Não consigo entrar no ERP","body":"Desde esta manhã aparece invalid credentials."}'
```

## Executar localmente

```bash
python3 -m venv .venv
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Instalar primeiro o wheel CPU evita trazer dependências CUDA para o ambiente
local. O Dockerfile já faz esta instalação automaticamente.

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
curl http://localhost:8080/ready
```

Benchmark local de inferência (carrega o modelo uma vez, aquece e mede chamadas
repetidas):

```bash
.venv/bin/python -m benchmarks.inference --warmup 2 --runs 10
```
