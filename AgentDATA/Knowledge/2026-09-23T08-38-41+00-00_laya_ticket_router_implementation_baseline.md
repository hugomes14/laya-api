# Registro de conhecimento

## Metadata

- Timestamp: `2026-09-23T08:38:41+00:00`
- Autor: `agent`
- Assunto: baseline de arquitetura e operação do Laya Ticket Router
- Status: `ativo`
- Retestar em: antes do fine-tuning completo e antes de cada fase de deployment

## Achado

Este registo é a referência canónica de implementação para a primeira versão
do serviço. Define um microserviço Flask em Docker que usa Laya multilingual
para classificar tickets hierarquicamente e mantém o routing como lógica
determinística externa ao modelo.

## Contexto

O serviço recebe tickets internos e devolve `category`, `subcategory` e as
confianças associadas. A classificação não pode decidir equipa, pessoa, agente
de IA ou workflow. Essas decisões são configuradas por `routing.yaml` e devem
ter sempre fallback seguro para triagem humana.

O plano cobre 47 secções, da taxonomia e API até treino, calibração, feedback e
deployment progressivo. O estado atual inclui os Milestones 1 e 2: shell
Flask/Docker, `/health`, `/ready`, carga de Laya no startup, classificação
inicial de categoria por `POST /v1/classify-only` e benchmark local. A
classificação de subcategoria, taxonomia externa e routing continuam nos
milestones seguintes.

## Metodo

Foi feita a leitura integral da especificação de implementação antes da sua
retirada do repositório, com revisão das decisões já tomadas, milestones,
contratos de API, requisitos de segurança, restrições de hardware e critérios
de aceitação.

## Comandos

```bash
.venv/bin/pytest -q
docker compose config --quiet
```

## Evidencia

Fatos definidos no plano:

- O modelo usa duas decisões: `ticket -> category` e
  `ticket + category -> subcategory`.
- A taxonomia inicial contém `IT_SUPPORT`, `ACCESS_SECURITY`,
  `FINANCE_ADMIN`, `HR_PEOPLE`, `FACILITIES` e `OTHER`; deve residir em YAML.
- O routing deve priorizar regra exata, depois `category/*`, e por fim
  `HUMAN_TRIAGE`.
- Os thresholds de bootstrap são `0.55` para categoria e subcategoria. Baixa
  confiança, categoria desconhecida, erro do modelo ou regra ausente não podem
  perder tickets e devem encaminhar para triagem humana.
- A API alvo inclui `GET /health`, `GET /ready`, `POST /v1/classify`,
  `POST /v1/classify-only` e, numa fase posterior, `POST /v1/feedback`.
- Serving usa CPU no Xeon E5-1650 v2, com modelo carregado uma vez no startup,
  Gunicorn com um worker e uma thread e PyTorch configurado para quatro threads
  intra-op e uma inter-op. A NVIDIA K2000 não é suportada para este caso.
- O treino começa em CPU com benchmark obrigatório de 500--2.000 exemplos. A
  decisão para GPU externa depende de treino completo estimado acima de 24 h.
- Dados bootstrap devem ter proveniência, licença adequada e splits
  estratificados; não usar datasets `CC-BY-NC` na primeira versão.
- O modelo requer calibração no validation set, avaliação por classe e versão
  imutável acompanhada de metadata. A sugestão inicial para deployment
  controlado é category macro-F1 >= 0.85.
- O rollout é sequencial: bootstrap, shadow mode, assisted routing e AI
  routing. Não fazer auto-treino com previsões não validadas.

Evidência recolhida no Milestone 2, em 2026-09-23:

- `laya==0.3.5`, `torch==2.14.0`, `transformers==5.17.0`,
  `huggingface_hub==1.32.0`, `safetensors==0.8.0`, `tokenizers==0.23.2` e
  `numpy==2.5.3` carregaram o checkpoint multilingual com sucesso no ambiente
  local Python 3.14.4.
- Benchmark no Intel Xeon E5-1650 v2 (6 cores/12 threads), CPU, uma pergunta de
  categoria com seis opções, duas chamadas de aquecimento e dez medições:
  carga do modelo 81.78 s; inferência média 2255.5 ms, mediana 2330.3 ms, p95
  2437.1 ms, mínimo 1955.9 ms e máximo 2463.2 ms.
- A imagem Docker Python 3.12 foi construída com sucesso usando
  `torch==2.14.0+cpu` e as dependências acima.
- O endpoint implementado retorna categoria, confiança, probabilidades,
  versão do modelo e latência. Valida JSON, `subject` até 500 caracteres,
  `body` até 10.000 caracteres e request até 65.536 bytes.

## Codigo relevante

```text
AgentDATA/Knowledge/2026-09-23T08-38-41+00-00_laya_ticket_router_implementation_baseline.md
                                        # especificação canónica resumida
app/api.py                            # API, inicialização e readiness
app/classifier.py                     # wrapper do Laya multilingual
benchmarks/inference.py               # benchmark local CPU
Dockerfile                            # serving CPU com Gunicorn
docker-compose.yml                    # cache persistente e healthcheck
tests/test_api.py                     # contrato inicial de health/readiness
```

## Interpretacao

Fato observado: o plano separa explicitamente semântica do ticket e decisão
operacional. Inferência técnica: regras de routing, thresholds e destinos podem
evoluir sem retreinar o classificador, desde que a taxonomia permaneça
compatível e versionada.

Fato observado: as confianças controlam automation. Inferência técnica: uma
métrica global boa não é suficiente para automatizar classes sensíveis, em
particular `ACCESS_SECURITY`; é necessário avaliar recall, calibração e erros
por classe.

## Consequencia operacional

O Milestone 2 está concluído. O modelo carrega uma vez na factory do serviço;
`/ready` só responde pronto depois da carga. O endpoint atual classifica apenas
a categoria. O próximo passo é o Milestone 3: mover a taxonomia para YAML,
implementar classificação hierárquica e confidence handling.

Qualquer alteração futura deve preservar:

- classificação hierárquica;
- routing determinístico fora do Laya;
- fallback seguro para `HUMAN_TRIAGE`;
- rastreabilidade de previsão, correção humana, dataset e versão de modelo;
- separação entre treino, calibration e test.

## Riscos e limites

- Os thresholds e a meta de macro-F1 são valores iniciais, não garantias de
  produção; precisam de tickets reais validados.
- A medição atual é de uma decisão de categoria no Xeon indicado; não estima
  duração de fine-tuning nem desempenho de carga concorrente.
- Os datasets públicos e sintéticos não substituem progressivamente dados reais
  corrigidos por humanos.
- A especificação original foi retirada após esta consolidação; detalhes novos
  devem ser registados diretamente neste baseline ou em registos específicos.

## Pendencias

1. Criar no Milestone 3 `taxonomy.yaml`, classificação hierárquica e confidence
   handling, incluindo testes unitários.
2. Criar no Milestone 4 `routing.yaml`, engine de fallbacks e testes unitários.
3. Antes do treino completo, implementar o benchmark de treino e registrar a
   decisão CPU versus GPU com dados medidos.
