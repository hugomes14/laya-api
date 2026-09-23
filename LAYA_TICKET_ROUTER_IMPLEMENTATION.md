# Laya Ticket Classifier — Especificação de Implementação

## 1. Objetivo

Implementar um microserviço **Docker + Flask** que recebe tickets internos, usa o **Laya multilingual** para classificar cada ticket em:

- `category`
- `subcategory`
- `category_confidence`
- `subcategory_confidence`

O Laya **não decide** se o ticket é tratado por uma pessoa, agente de IA ou workflow.

Essa decisão pertence a um **routing engine determinístico**, configurado manualmente com base em `category + subcategory`.

Fluxo:

```text
Ticket
  |
  v
Flask API
  |
  v
Laya classifier
  |
  +--> category
  +--> subcategory
  +--> confidence
  |
  v
Routing Engine
  |
  +--> HUMAN
  +--> AI_AGENT
  +--> WORKFLOW
  +--> HUMAN_TRIAGE
```

A primeira versão será treinada com datasets públicos/sintéticos. Em produção, todos os tickets e correções humanas serão guardados para criar progressivamente um dataset específico da empresa.

---

# 2. Princípios de arquitetura

## 2.1 Separar classificação de routing

O modelo responde:

> "Que tipo de ticket é este?"

A aplicação responde:

> "O que fazemos com este tipo de ticket?"

Não treinar o Laya para escolher diretamente:

- pessoa;
- agente IA;
- workflow;
- equipa específica;
- colaborador específico.

Isso permite alterar as regras operacionais sem novo treino.

Exemplo:

```text
Hoje:
IT_SUPPORT / printer
-> HUMAN_IT

Mais tarde:
IT_SUPPORT / printer
-> AI_IT_AGENT
```

O classificador continua igual.

---

# 3. Taxonomia inicial

A taxonomia deve ser pequena, estável e configurável.

## 3.1 Categorias principais recomendadas

```text
IT_SUPPORT
ACCESS_SECURITY
FINANCE_ADMIN
HR_PEOPLE
FACILITIES
OTHER
```

## 3.2 Subcategorias iniciais

### IT_SUPPORT

```text
software
hardware
network
printer
email
erp
application_error
performance
other_it
```

### ACCESS_SECURITY

```text
password_reset
account_creation
account_locked
permissions
privileged_access
mfa
security_incident
other_access
```

### FINANCE_ADMIN

```text
invoice
payment
expense
supplier
procurement
reimbursement
other_finance
```

### HR_PEOPLE

```text
leave
payroll
employment_contract
onboarding
offboarding
benefits
other_hr
```

### FACILITIES

```text
air_conditioning
electricity
furniture
cleaning
building_access
maintenance
other_facilities
```

### OTHER

```text
general
```

A taxonomia deve viver num ficheiro de configuração e não diretamente espalhada pelo código.

---

# 4. Classificação hierárquica

Não usar uma única decisão com todas as subcategorias.

Executar:

```text
Passo 1
ticket -> category

Passo 2
ticket + category -> subcategory específica dessa category
```

Exemplo:

```text
ticket:
"O Outlook deixou de sincronizar desde esta manhã"

category:
IT_SUPPORT

subcategories consideradas:
software
hardware
network
printer
email
erp
application_error
performance
other_it

resultado:
email
```

Isto reduz competição entre labels semanticamente não relacionadas.

---

# 5. Routing Engine

O routing é configurado manualmente.

Exemplo de configuração:

```yaml
routes:

  ACCESS_SECURITY:
    password_reset:
      destination: AI_IDENTITY_AGENT

    account_locked:
      destination: AI_IDENTITY_AGENT

    privileged_access:
      destination: HUMAN_SECURITY

    security_incident:
      destination: HUMAN_SECURITY

  IT_SUPPORT:
    printer:
      destination: AI_IT_AGENT

    email:
      destination: AI_IT_AGENT

    server_outage:
      destination: HUMAN_IT

  FINANCE_ADMIN:
    invoice:
      destination: AI_FINANCE_AGENT

    payment:
      destination: HUMAN_FINANCE

  HR_PEOPLE:
    "*":
      destination: HUMAN_HR

  FACILITIES:
    "*":
      destination: HUMAN_FACILITIES

  OTHER:
    "*":
      destination: HUMAN_TRIAGE
```

O routing engine deve suportar:

1. regra exata `category + subcategory`;
2. fallback `category + "*"`;
3. fallback global `HUMAN_TRIAGE`.

---

# 6. Confidence gating

Mesmo após fine-tuning, nunca encaminhar cegamente todas as previsões.

Valores iniciais apenas para bootstrap:

```text
CATEGORY_THRESHOLD    = 0.55
SUBCATEGORY_THRESHOLD = 0.55
```

Lógica:

```python
if category_confidence < CATEGORY_THRESHOLD:
    destination = "HUMAN_TRIAGE"

elif subcategory_confidence < SUBCATEGORY_THRESHOLD:
    destination = f"HUMAN_{category}"

else:
    destination = routing_table[category][subcategory]
```

Os thresholds definitivos devem ser ajustados depois de existir um conjunto de tickets reais validados.

---

# 7. API Flask

## 7.1 Endpoints

### `GET /health`

Resposta:

```json
{
  "status": "ok",
  "model_loaded": true,
  "model": "laya-multilingual"
}
```

### `GET /ready`

Deve devolver `200` apenas depois de o modelo estar completamente carregado.

### `POST /v1/classify`

Request:

```json
{
  "ticket_id": "INC-12345",
  "subject": "Não consigo entrar no ERP",
  "body": "Desde esta manhã aparece invalid credentials."
}
```

Response:

```json
{
  "ticket_id": "INC-12345",
  "classification": {
    "category": "IT_SUPPORT",
    "subcategory": "erp",
    "category_confidence": 0.87,
    "subcategory_confidence": 0.81
  },
  "routing": {
    "destination": "AI_IT_AGENT",
    "rule": "IT_SUPPORT/erp"
  },
  "model": {
    "name": "laya-multilingual",
    "version": "ticket-router-v1"
  },
  "latency_ms": 2140
}
```

### `POST /v1/classify-only`

Opcional.

Devolve apenas classificação, sem routing.

Útil para:

- avaliação;
- backfills;
- criação de datasets;
- debugging.

---

# 8. Estrutura do projeto

```text
laya-ticket-router/
|
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── classifier.py
│   ├── routing.py
│   ├── schemas.py
│   ├── config.py
│   └── logging_config.py
│
├── config/
│   ├── taxonomy.yaml
│   └── routing.yaml
│
├── training/
│   ├── download_datasets.py
│   ├── normalize.py
│   ├── mapping.yaml
│   ├── split_dataset.py
│   ├── validate_dataset.py
│   ├── train.py
│   ├── calibrate.py
│   └── evaluate.py
│
├── tests/
│   ├── test_api.py
│   ├── test_routing.py
│   ├── test_classifier.py
│   └── fixtures/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── README.md
│
├── models/
│   └── .gitkeep
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .dockerignore
├── .env.example
└── README.md
```

---

# 9. Implementação do classifier

O processo Flask deve carregar o modelo **uma única vez durante o arranque**.

Não carregar o modelo por request.

Configuração inicial para o servidor atual:

```python
import os

os.environ["USE_TF"] = "0"

import torch
import laya

torch.set_num_threads(4)
torch.set_num_interop_threads(1)

agent = laya.load(
    "convaiinnovations/laya",
    subfolder="multilingual",
    device="cpu",
)
```

O servidor testado tem:

```text
Intel Xeon E5-1650 v2
6 cores / 12 threads
30 GiB RAM
AVX
sem AVX2
```

Benchmark observado:

```text
1 pergunta:
~0.96 s

3 perguntas:
~3.15-3.20 s

5 perguntas:
~5.5-6.5 s
```

Para o volume interno esperado isto é aceitável.

Configuração recomendada:

```text
PyTorch intra-op threads: 4
PyTorch inter-op threads: 1
```

Não utilizar a NVIDIA K2000 para este serviço.

---

# 10. Pergunta de categoria

Exemplo conceptual:

```python
CATEGORY_QUESTION = {
    "category": {
        "type": "choice",
        "instructions": (
            "Classify this internal company support ticket into the "
            "single most appropriate operational category."
        ),
        "criteria": {
            "IT_SUPPORT": (
                "Software, hardware, ERP, applications, email, printers, "
                "networking, technical failures and ordinary IT support."
            ),
            "ACCESS_SECURITY": (
                "Accounts, passwords, MFA, permissions, administrator access, "
                "security incidents and access control."
            ),
            "FINANCE_ADMIN": (
                "Invoices, payments, expenses, suppliers, procurement "
                "and finance administration."
            ),
            "HR_PEOPLE": (
                "Employees, leave, payroll, contracts, onboarding, "
                "offboarding and human resources."
            ),
            "FACILITIES": (
                "Building, air conditioning, electricity, furniture, "
                "cleaning, physical access and physical maintenance."
            ),
            "OTHER": (
                "Requests which clearly do not belong to the other categories."
            )
        }
    }
}
```

Manter as instruções do classificador estáveis entre treino e produção.

---

# 11. Perguntas de subcategoria

Criar uma pergunta por categoria.

Exemplo:

```python
IT_SUBCATEGORY = {
    "subcategory": {
        "type": "choice",
        "instructions": (
            "Classify this IT support ticket into the most appropriate "
            "IT subcategory."
        ),
        "criteria": {
            "software": "Software installation, configuration or usage.",
            "hardware": "Physical computer or peripheral hardware.",
            "network": "Connectivity, Wi-Fi, LAN, VPN or network.",
            "printer": "Printers, scanners and printing.",
            "email": "Email clients, mailboxes, Outlook and mail delivery.",
            "erp": "ERP application access or functionality.",
            "application_error": "Application errors, crashes or failures.",
            "performance": "Slowness and performance problems.",
            "other_it": "Other IT support request."
        }
    }
}
```

O mesmo padrão deve existir para cada categoria.

---

# 12. Concorrência

O Laya é CPU-bound neste servidor.

Inicialmente utilizar:

```text
Gunicorn workers: 1
threads: 1
```

Exemplo:

```bash
gunicorn \
  --bind 0.0.0.0:8080 \
  --workers 1 \
  --threads 1 \
  --timeout 120 \
  "app.api:create_app()"
```

Motivos:

- cada worker carregaria uma cópia do modelo;
- múltiplas inferências simultâneas competiriam pelos mesmos cores;
- o volume de tickets é baixo;
- simplicidade operacional é mais importante que throughput máximo.

Se houver pedidos simultâneos, poderão ficar em fila durante alguns segundos.

Antes de aumentar workers, medir:

- RAM;
- CPU;
- p50;
- p95;
- tamanho da fila.

---

# 13. Dockerfile

Base recomendada:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV USE_TF=0
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config

EXPOSE 8080

CMD [
  "gunicorn",
  "--bind", "0.0.0.0:8080",
  "--workers", "1",
  "--threads", "1",
  "--timeout", "120",
  "app.api:create_app()"
]
```

Usar Python 3.12 em vez do Python 3.14 do primeiro teste para uma base de produção mais conservadora em compatibilidade de bibliotecas.

---

# 14. requirements.txt

Versões devem ser fixadas depois de validar a imagem final.

Exemplo inicial:

```text
Flask
gunicorn
laya==0.3.5
torch
transformers
huggingface_hub
PyYAML
pydantic
```

Depois do primeiro build funcional:

```bash
pip freeze
```

e fixar versões exatas.

---

# 15. docker-compose.yml

```yaml
services:

  ticket-router:
    build: .
    container_name: laya-ticket-router

    ports:
      - "8080:8080"

    environment:
      USE_TF: "0"
      OMP_NUM_THREADS: "4"
      MKL_NUM_THREADS: "4"
      HF_HOME: "/models/huggingface"

    volumes:
      - laya-model-cache:/models/huggingface
      - ./config:/app/config:ro

    restart: unless-stopped

    healthcheck:
      test:
        [
          "CMD",
          "curl",
          "-f",
          "http://localhost:8080/health"
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 180s

volumes:
  laya-model-cache:
```

Persistir a cache Hugging Face para evitar novo download a cada rebuild/restart.

---

# 16. Download do modelo

Idealmente descarregar o checkpoint durante deployment ou warm-up e persistir em volume.

Não incluir os ~650 MB de pesos diretamente no Git.

Opções:

1. volume persistente Hugging Face;
2. download na pipeline de deployment;
3. imagem Docker privada com o checkpoint incluído, se for necessário deployment completamente offline.

Para ambientes sem Internet, preparar a imagem ou volume antecipadamente.

---

# 17. Dataset inicial

## 17.1 Dataset principal

Utilizar como bootstrap:

```text
KameronB/synthetic-it-callcenter-tickets
```

Características úteis:

- ~27.6k tickets;
- `category`;
- `subcategory`;
- `assignment_group`;
- `short_description`;
- `content`;
- licença Apache-2.0.

Referência:

https://huggingface.co/datasets/KameronB/synthetic-it-callcenter-tickets

## 17.2 Dataset complementar

```text
cngchis/Support-Ticket-Router-12K-Cleaned
```

Características:

- ~11.7k exemplos;
- routing simples;
- labels como billing/technical/etc.;
- licença Apache-2.0.

Referência:

https://huggingface.co/datasets/cngchis/Support-Ticket-Router-12K-Cleaned

## 17.3 Não depender de datasets NC

Evitar na primeira implementação datasets com licença `CC-BY-NC` para não introduzir dúvidas sobre utilização empresarial.

---

# 18. Normalização do dataset

Converter as labels dos datasets públicos para a taxonomia interna.

Formato normalizado:

```json
{
  "id": "source-123",
  "source": "kameronb",
  "subject": "User cannot login to ERP",
  "body": "User receives authentication error...",
  "category": "IT_SUPPORT",
  "subcategory": "erp"
}
```

Guardar em JSONL.

---

# 19. Regras de qualidade do dataset

Antes do treino:

- remover duplicados;
- remover tickets vazios;
- remover labels ambíguas;
- verificar distribuição de classes;
- limitar exemplos quase idênticos;
- garantir separação entre treino/test sem duplicados semânticos óbvios;
- não deixar templates iguais espalhados entre `train` e `test`.

Target inicial:

```text
train      80%
validation 10%
test       10%
```

Usar split estratificado por:

```text
category
subcategory
```

---

# 20. Balanceamento

Não treinar num dataset extremamente enviesado.

Objetivo inicial aproximado por categoria:

```text
IT_SUPPORT        2k-4k
ACCESS_SECURITY   2k-4k
FINANCE_ADMIN     2k-4k
HR_PEOPLE         2k-4k
FACILITIES        2k-4k
OTHER             1k-2k
```

Não é obrigatório atingir exatamente estes números.

Se um dataset público não tiver exemplos suficientes para uma categoria:

1. procurar outro dataset com licença adequada;
2. criar dados sintéticos controlados;
3. reduzir/alterar a taxonomia;
4. não inventar uma classe mal suportada só para manter simetria.

Qualidade > volume.

---

# 21. Dados sintéticos

Dados sintéticos podem ser utilizados no bootstrap.

Devem variar:

- vocabulário;
- comprimento;
- erros ortográficos;
- português PT;
- linguagem informal;
- referências a aplicações internas genéricas;
- pedidos diretos e indiretos;
- mensagens ambíguas.

Exemplos:

```text
"não consigo imprimir no escritório"
-> IT_SUPPORT / printer

"preciso de admin no servidor de produção"
-> ACCESS_SECURITY / privileged_access

"preciso novamente da fatura de agosto"
-> FINANCE_ADMIN / invoice

"quantos dias de férias ainda tenho?"
-> HR_PEOPLE / leave

"o ar condicionado da sala 3 deixou de funcionar"
-> FACILITIES / air_conditioning
```

Os dados sintéticos devem ser marcados:

```json
{
  "source": "synthetic"
}
```

Nunca misturar origem sem tracking.

---

# 22. Fine-tuning do Laya

O projeto Laya fornece um notebook oficial para fine-tuning com RLCD:

```text
notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb
```

Referência:

https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb

Segundo a documentação do projeto, um exemplo de treino completo utiliza aproximadamente:

```text
~30k perguntas
4 epochs
2 x NVIDIA T4
~4-5 horas
```

O pipeline oficial inclui:

1. construção do dataset;
2. RLCD fine-tuning;
3. fitting das temperaturas de calibração;
4. avaliação;
5. export/push do checkpoint.

Para este projeto, o objetivo inicial é mais simples:

```text
ticket
  -> category
  -> subcategory
```

Não é necessário assumir desde o início que o treino oficial completo, com o mesmo número de perguntas e epochs, será a configuração final.

A estratégia deve começar por um treino pequeno e mensurável.

---

# 23. Hardware de treino disponível

Servidor atual:

```text
CPU:
Intel Xeon E5-1650 v2
6 cores / 12 threads
3.5 GHz base
3.9 GHz turbo
AVX
sem AVX2

RAM:
30 GiB

GPU:
NVIDIA K2000
2 GB VRAM
Kepler / compute capability antiga
```

A NVIDIA K2000 não deve ser usada para treino do Laya porque não é adequada ao stack CUDA/PyTorch atual.

O treino local deverá ser feito em **CPU**.

O Xeon consegue executar inferência corretamente e tem RAM suficiente para experimentar treino, mas é uma CPU antiga e sem AVX2.

Benchmarks de inferência já observados no servidor:

```text
1 decisão:
~0.96 s

3 decisões:
~3.15-3.20 s

5 decisões:
~5.5-6.5 s
```

Estes números não devem ser usados diretamente para estimar treino, porque fine-tuning adiciona:

- backward pass;
- gradientes;
- optimizer states;
- atualização de parâmetros;
- batching;
- várias epochs;
- e, se usado, o custo adicional do RLCD.

Por isso, a duração real deve ser medida.

---

# 24. Política de treino: CPU primeiro, GPU como fallback

A primeira opção de treino deve ser o servidor atual, desde que o benchmark mostre uma duração aceitável.

Não decidir antecipadamente que o treino CPU é demasiado lento.

Fluxo obrigatório:

```text
dataset bootstrap
      |
      v
selecionar pequena amostra
      |
      v
benchmark de treino CPU
      |
      v
medir:
  - segundos por step
  - exemplos por segundo
  - RAM máxima
  - duração da epoch
      |
      v
extrapolar treino completo
      |
      +------------------------------+
      |                              |
      v                              v
tempo aceitável                  tempo excessivo
      |                              |
      v                              v
treino no Xeon                 treino em GPU externa
```

---

# 25. Benchmark obrigatório antes do full training

Criar:

```text
training/benchmark_train.py
```

O benchmark deve conseguir selecionar automaticamente uma pequena fração do dataset.

Configuração inicial recomendada:

```text
500 exemplos
1 epoch
batch size mínimo que caiba confortavelmente
CPU only
4 threads
```

Depois repetir, se necessário, com:

```text
1.000 exemplos
2.000 exemplos
```

O benchmark deve guardar:

```json
{
  "samples": 500,
  "steps": 0,
  "epoch_seconds": 0,
  "seconds_per_step": 0,
  "samples_per_second": 0,
  "peak_memory_mb": 0,
  "estimated_full_epoch_hours": 0
}
```

A estimativa deve ser baseada em dados medidos e não numa extrapolação da inferência.

---

# 26. Critério para decidir CPU vs GPU

Usar como regra operacional inicial:

```text
full training estimado <= 24 horas
-> CPU local é aceitável

full training estimado > 24 horas
-> considerar GPU externa
```

O valor de 24 horas é um limite operacional, não técnico.

Pode ser alterado se a empresa aceitar treinos de fim de semana ou overnight.

Exemplo:

```text
8-12 horas
-> muito aceitável localmente

18-24 horas
-> aceitável se treino for ocasional

2-3 dias
-> possível, mas começa a dificultar iteração

5+ dias
-> preferir GPU
```

A razão principal para usar GPU não é apenas concluir um treino, mas permitir:

- testar hiperparâmetros;
- corrigir o dataset;
- repetir treino;
- comparar versões;
- fazer experiências sem bloquear dias inteiros.

---

# 27. Estratégia de treino progressiva

Não começar imediatamente com dezenas de milhares de exemplos e várias epochs.

## Fase 1 — Pipeline smoke test

```text
100-500 exemplos
1 epoch
```

Objetivo:

- verificar que o pipeline funciona;
- validar formato dos dados;
- confirmar que loss desce;
- confirmar consumo de RAM;
- confirmar que checkpoints são gerados.

## Fase 2 — Benchmark

```text
500-2.000 exemplos
1 epoch
```

Objetivo:

- medir throughput real;
- estimar duração do full training;
- escolher CPU ou GPU.

## Fase 3 — Primeiro modelo utilizável

Exemplo inicial:

```text
5.000-10.000 exemplos
1-2 epochs
```

Objetivo:

- medir qualidade;
- avaliar category/subcategory;
- verificar se o fine-tuning já melhora claramente o zero-shot.

## Fase 4 — Full training

Apenas depois de validar os resultados anteriores.

Exemplo:

```text
10.000-20.000 exemplos
2-4 epochs
```

O volume final deve ser definido pelos resultados e não apenas pela quantidade de dados disponível.

---

# 28. Estratégia de treino simplificado antes de RLCD completo

O pipeline oficial do Laya utiliza RLCD para decisões calibradas.

Para este projeto, o primeiro problema é essencialmente:

```text
texto
-> classe
```

por isso deve ser considerada uma fase experimental de treino supervisionado mais simples antes de reproduzir todo o pipeline RLCD.

Possibilidades a avaliar:

```text
A) full RLCD
B) supervised fine-tuning
C) supervised fine-tuning + temperature calibration
D) treino parcial / layers congeladas
```

Não assumir que todas estão diretamente expostas pela API de alto nível do pacote Laya.

Se necessário, adaptar o notebook/código de treino oficial.

Objetivo da primeira versão:

```text
boa classificação
+
probabilidades suficientemente úteis
```

e não reproduzir todas as características do treino original se isso tornar a iteração CPU impraticável.

---

# 29. Experiência com layers congeladas

Se o full fine-tuning em CPU for demasiado lento, experimentar treino parcial.

Exemplo conceptual:

```text
mmBERT backbone
████████████████████████
congelado

últimas layers
████
treináveis

decision head
██
treinável
```

Benefícios possíveis:

- menos backward;
- menos optimizer state;
- menor uso de RAM;
- menor duração por step.

Trade-off:

- menor capacidade de adaptação;
- pode não aprender suficientemente bem o domínio;
- precisa de avaliação independente.

Nunca assumir que treino parcial é equivalente ao full fine-tuning.

---

# 30. Calibration

Após o fine-tuning, executar fitting/calibração das temperaturas no validation set.

Isto é importante porque produção usará confidence thresholds.

Exemplo:

```python
if category_confidence < CATEGORY_THRESHOLD:
    destination = "HUMAN_TRIAGE"
```

Esses thresholds só são úteis se os scores estiverem razoavelmente calibrados.

Nunca ajustar temperaturas usando o test set.

Usar:

```text
train      -> treino
validation -> calibration + tuning
test       -> avaliação final
```

---

# 31. GPU externa como fallback

Se o benchmark CPU mostrar tempos demasiado altos, usar GPU apenas para treino.

Opções:

```text
Kaggle
Google Colab
servidor GPU temporário
cloud GPU
```

Depois copiar apenas o checkpoint final para produção.

Fluxo:

```text
Dataset
   |
   +-----------------------------+
   |                             |
   v                             v
CPU local                   GPU externa
(se aceitável)              (fallback)
   |                             |
   +-------------+---------------+
                 |
                 v
        fine-tuned checkpoint
                 |
                 v
            calibration
                 |
                 v
             evaluation
                 |
                 v
         versioned artifact
                 |
                 v
          production Xeon
```

Treino e serving não precisam de acontecer na mesma máquina.

---

# 32. Versionamento de modelos

Cada treino deve criar uma versão imutável.

Exemplo:

```text
ticket-router-v1.0.0
ticket-router-v1.1.0
ticket-router-v2.0.0
```

Guardar junto do modelo:

```json
{
  "model_version": "ticket-router-v1.0.0",
  "base_model": "convaiinnovations/laya-multilingual",
  "dataset_version": "bootstrap-v1",
  "taxonomy_version": "1",
  "trained_at": "YYYY-MM-DD",
  "metrics": {
    "category_accuracy": 0.0,
    "subcategory_accuracy": 0.0,
    "category_macro_f1": 0.0,
    "subcategory_macro_f1": 0.0
  }
}
```

---

# 33. Avaliação antes de produção

Não avaliar apenas accuracy global.

Medir:

```text
category:
  accuracy
  macro F1
  confusion matrix
  per-class precision
  per-class recall

subcategory:
  accuracy
  macro F1
  confusion matrix
  per-class precision
  per-class recall

confidence:
  calibration / ECE
  accuracy vs confidence
```

Especialmente importante:

```text
ACCESS_SECURITY false negatives
```

e confusões:

```text
IT_SUPPORT <-> ACCESS_SECURITY
IT_SUPPORT <-> FACILITIES
FINANCE_ADMIN <-> HR_PEOPLE
```

---

# 34. Critério inicial de aceitação

Sugestão para primeiro deployment controlado:

```text
Category macro F1 >= 0.85
```

Subcategorias poderão inicialmente ter threshold inferior, desde que baixa confiança resulte em triagem humana.

Não bloquear o projeto apenas por uma métrica global se o comportamento por classe estiver bem compreendido.

Primeira fase de produção deve ser considerada "shadow / assisted routing":

```text
Laya recomenda
+
humano confirma/corrige
```

antes de automatizar categorias sensíveis.

---

# 35. Logging em produção

Guardar cada classificação.

Exemplo:

```json
{
  "ticket_id": "INC-12345",
  "created_at": "2026-09-22T15:00:00Z",

  "input": {
    "subject": "...",
    "body": "..."
  },

  "prediction": {
    "category": "IT_SUPPORT",
    "subcategory": "erp",
    "category_confidence": 0.87,
    "subcategory_confidence": 0.81
  },

  "routing": {
    "destination": "AI_IT_AGENT"
  },

  "model_version": "ticket-router-v1.0.0",

  "feedback": null
}
```

Aplicar políticas internas de retenção e acesso, porque tickets podem conter dados pessoais ou confidenciais.

---

# 36. Feedback / correção

Adicionar posteriormente endpoint ou integração equivalente:

### `POST /v1/feedback`

```json
{
  "ticket_id": "INC-12345",
  "correct_category": "ACCESS_SECURITY",
  "correct_subcategory": "account_locked",
  "resolved_by": "human",
  "routing_was_correct": false
}
```

Nunca substituir silenciosamente a previsão original.

Guardar:

```text
predicted_category
predicted_subcategory

final_category
final_subcategory
```

Isso permite medir o modelo e construir treino futuro.

---

# 37. Dataset real da empresa

À medida que tickets forem entrando, construir:

```json
{
  "subject": "...",
  "body": "...",

  "predicted_category": "IT_SUPPORT",
  "predicted_subcategory": "erp",

  "final_category": "IT_SUPPORT",
  "final_subcategory": "erp",

  "destination": "AI_IT_AGENT",

  "resolved_by": "ai",

  "escalated": false
}
```

Após volume suficiente, este dataset deve progressivamente substituir dados públicos.

---

# 38. Ciclo de melhoria

```text
                     Production
                         |
                         v
                  incoming tickets
                         |
                         v
                 model predictions
                         |
                         v
              human/AI resolution
                         |
                         v
                  corrections
                         |
                         v
                 validated dataset
                         |
                         v
                   retraining
                         |
                         v
                  model vNext
                         |
                         v
                    evaluation
                         |
                         +------> production
```

Não fazer auto-treino com previsões não validadas.

---

# 39. Métricas operacionais

Exportar pelo menos:

```text
requests_total
classification_errors_total
classification_latency_seconds
routing_destination_total
low_confidence_total
model_load_seconds
```

Mais tarde:

```text
prediction_corrected_total
category_accuracy
subcategory_accuracy
ai_escalation_rate
```

---

# 40. Tratamento de erros

Se o Laya falhar:

```text
destination = HUMAN_TRIAGE
```

Se category for desconhecida:

```text
destination = HUMAN_TRIAGE
```

Se confidence for baixa:

```text
destination = HUMAN_TRIAGE
```

Se routing.yaml não tiver uma regra:

```text
destination = HUMAN_TRIAGE
```

O serviço nunca deve perder um ticket por falha de classificação.

---

# 41. Segurança da API

Inicialmente:

- serviço apenas em rede interna;
- autenticação entre serviços;
- limite de tamanho de request;
- timeout;
- logs sem tokens/secrets;
- não expor Hugging Face token em logs;
- Docker sem modo privilegiado;
- filesystem read-only onde possível.

Se existir reverse proxy:

```text
Client / Ticket System
        |
        v
    Nginx / Traefik
        |
        v
Laya Ticket Router
```

---

# 42. Limites de input

Definir limites explícitos.

Exemplo:

```text
subject <= 500 caracteres
body    <= 10.000 caracteres
```

Como o modelo tem orçamento de contexto limitado, textos excessivamente longos devem ser truncados de forma controlada.

Estratégia inicial:

```text
subject completo
+
primeiros N caracteres do body
```

Não truncar o assunto primeiro.

---

# 43. Testes obrigatórios

## Unit tests

Routing:

```text
IT_SUPPORT / printer
-> destino configurado
```

Fallback:

```text
categoria desconhecida
-> HUMAN_TRIAGE
```

Low confidence:

```text
confidence < threshold
-> HUMAN_TRIAGE
```

## API tests

```text
GET /health
GET /ready
POST /v1/classify
invalid JSON
missing subject/body
oversized request
```

## Model integration tests

Criar um fixture estável com 20-50 tickets.

Verificar regressões entre versões do modelo.

---

# 44. Deployment inicial

## Fase A — Bootstrap

- montar taxonomia;
- preparar dataset público;
- treinar Laya;
- avaliar offline.

## Fase B — Shadow mode

- receber tickets reais;
- Laya classifica;
- classificação não controla routing automaticamente;
- guardar previsão;
- humano valida implicitamente através da fila final.

## Fase C — Assisted routing

Automatizar apenas categorias/subcategorias de alta precisão.

## Fase D — AI routing

Ligar determinadas subcategorias a agentes IA:

```text
ACCESS_SECURITY/password_reset
-> AI_IDENTITY_AGENT

IT_SUPPORT/printer
-> AI_IT_AGENT

FINANCE_ADMIN/invoice
-> AI_FINANCE_AGENT
```

Continuar a manter routing fora do modelo.

---

# 45. Plano de implementação para o agente

## Milestone 1

Criar estrutura do projeto.

Entregáveis:

```text
Dockerfile
docker-compose.yml
Flask app
/health
/ready
```

## Milestone 2

Integrar Laya multilingual.

Entregáveis:

```text
classifier.py
model load no startup
/v1/classify-only
benchmark local
```

## Milestone 3

Implementar taxonomia hierárquica.

Entregáveis:

```text
category classification
subcategory classification
confidence handling
taxonomy.yaml
```

## Milestone 4

Implementar routing engine.

Entregáveis:

```text
routing.yaml
routing.py
fallbacks
unit tests
```

## Milestone 5

Construir dataset bootstrap.

Entregáveis:

```text
download script
mapping rules
normalized JSONL
train/validation/test split
distribution report
```

## Milestone 6

Benchmark e fine-tuning.

Entregáveis:

```text
training/benchmark_train.py
benchmark CPU com 500-2.000 exemplos
estimativa de duração por epoch
decisão documentada CPU vs GPU
training notebook/script
checkpoint
calibration
evaluation report
model metadata
```

Regra:

```text
se duração estimada for operacionalmente aceitável:
    treinar no Xeon
senão:
    usar GPU externa
```

## Milestone 7

Deploy inicial.

Entregáveis:

```text
Docker image
persistent HF/model cache
healthcheck
logging
metrics
```

## Milestone 8

Feedback loop.

Entregáveis:

```text
ticket prediction log
human correction storage
/v1/feedback or equivalent integration
dataset export
```

---

# 46. Decisões já tomadas

```text
Framework API:
Flask

Deployment:
Docker

Modelo:
Laya multilingual

Produção:
CPU

Servidor:
Xeon E5-1650 v2

GPU K2000:
não utilizar

Modelo carregado:
uma vez no startup

Classificação:
category + subcategory

Routing:
determinístico e externo ao Laya

Destino:
human / AI agent / workflow

Dataset inicial:
público + sintético

Dataset futuro:
tickets reais validados

Treino:
CPU local primeiro, condicionado a benchmark
GPU externa como fallback/aceleração

Benchmark de treino:
obrigatório antes do full fine-tuning

Serving:
servidor atual
```

---

# 47. Resumo técnico

Arquitetura final pretendida:

```text
             Ticket System
                   |
                   | HTTP
                   v
        +----------------------+
        | Flask Ticket Router  |
        +----------------------+
                   |
                   v
        +----------------------+
        | Laya Multilingual    |
        | category/subcategory |
        +----------------------+
                   |
                   v
        +----------------------+
        | Confidence Gate      |
        +----------------------+
                   |
                   v
        +----------------------+
        | Routing Engine       |
        | routing.yaml         |
        +----------------------+
            |       |       |
            v       v       v
          Human    AI    Workflow
                   |
                   v
           Resolution / Feedback
                   |
                   v
            Training Dataset
```

A responsabilidade do Laya termina em:

```text
category
subcategory
confidence
```

Toda a lógica de negócio e automação permanece controlada pelo sistema.
