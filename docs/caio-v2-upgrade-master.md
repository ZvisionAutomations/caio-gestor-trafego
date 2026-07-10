# Caio/Hermes v2 — Documento Mestre de Upgrade

> **Status:** Design consolidado · pronto para quebra em stories
> **Data:** 2026-07-04
> **Pipeline:** Research (offline+live) → Grill-me → Brainstorm (paid media) → Arquitetura (@architect) → **este doc** → Stories → Implementação
> **Fontes vivas:** ver seção 4 (research) e rodapé.

---

## 1. Propósito

Consolidar, num único documento fonte-de-verdade, TODAS as melhorias planejadas para o **Caio/Hermes** — o agente autônomo de gestão de tráfego Meta Ads da Raiz Vital — validadas por pesquisa 2026, decididas em grill-me, calibradas em brainstorm com o squad de paid media e desenhadas tecnicamente pelo architect. É o input direto para as stories.

## 2. Estado atual (produção)

- Caio = agente Meta Ads 24/7 sobre **Hermes Agent v0.18** (systemd), cérebro **GLM-4.7-flash**, MCP `meta-ads`. **JÁ EM PRODUÇÃO** (Telegram + cronjobs) na VPS Hostinger `187.127.44.191`.
- Conta Meta `act_1745516809747438`. Venda 100% por **WhatsApp / Click-to-WhatsApp (CTWA)**. Sem pixel. Volume baixo (<50 compras/sem).
- **Gestor puro:** ingere criativos prontos de pasta de handoff, sobe/otimiza/pausa/escala. **NÃO cria copy nem criativo.**

### 2.1 Divisão de responsabilidades (fronteira dura)

| Quem | O quê |
|---|---|
| **Operador (Miguel) + framework Synapse** | Cria TODOS os criativos e copy — via **squads de copy + criação de conteúdo** e **Higgsfield (MCP/CLI)**. Monta os pacotes (asset + manifest: copy, targeting, budget, tipo, score de viralização) e deposita organizado na pasta de handoff (GDrive). |
| **Caio/Hermes** | SÓ **sobe** os criativos prontos pra Meta e **gerencia** (otimiza/pausa/escala/relatório) dentro dos guardrails. Nunca gera nem edita criativo/copy. |

Consequência: a qualidade e o volume de criativo são responsabilidade do fluxo de criação (Synapse+Higgsfield), não do Caio. O gargalo de "velocidade de produção criativa" (Risco 2, §5.5) é resolvido lá, não aqui.
- Guardrails atuais: CPL>R$35 pausa; tetos R$50/adset, R$300/conta; escala/ativação = aprovação humana.
- **Restrição transversal:** por estar em produção, todo rollout é faseado, com backup e feature flags.

## 3. Mapa de decisões (grill-me)

| # | Decisão | Resultado | Fase |
|---|---|---|---|
| 1 | Atribuição | CAPI Business Messaging: `ctwa_clid`→persist→`Purchase` na venda + `InitiateCheckout` (Pix) como proxy <50/sem | 1 |
| 2 | Arquitetura | State machine por adset + camada **Guardian** agora; Orchestrator/Executor incremental | 1 |
| 3 | v2 MoA (story-085) | Reescopar **advisory-only** (scoring/recomendação, nunca execução) | 2 |
| 4 | Motor de regras | Framework multi-condição completo; thresholds **config-driven** | 1 |
| 5 | Handoff/criativo | Versão completa; acesso via **GDrive** (decisão @architect) | 1 (acesso) / 2 (scoring) |
| + | Escopo extra | **Retargeting estruturado** + **lista compliance Health/Wellness** | 1 |

**Restrições transversais:** Caio em produção (rollout seguro) · LGPD (E.164 com 9º dígito + SHA-256 + legítimo interesse documentado) · schema-validation antes de tool call com ID de API.

## 4. Research 2026 (validado ao vivo)

- **Governed autonomy** é o padrão vencedor: spend caps + approval gates + audit trail + kill switch, humano dono da estratégia. Gartner 2026 (1.200 anunciantes): **+40-280% ROAS** vs manual; 15-25% de lift após estabilizar learning.
- **CAPI Business Messaging é nativo.** Elo = `ctwa_clid` do webhook `referral` do WhatsApp na 1ª mensagem; persistir por telefone (TTL 28-90d). Campos obrigatórios: `action_source:"business_messaging"`, `messaging_channel:"whatsapp"` — sem eles a Meta trata como conversão web e a atribuição quebra em silêncio.
- **`messaging_conversation_started` é sinal fraco** (até 90% abandonam antes de mandar msg). Sinal correto: `Purchase` via CAPI, ou `InitiateCheckout` (Pix) como proxy em volume baixo.
- **Pausa multi-condição** (nunca CPL isolado): `CPL>alvo E freq>3.5 E rodando>48-72h`. Escala **+20-25%/72h**; salto >2× = duplicar. Não editar durante learning (50 eventos/7d). Fadiga: `freq>3.5 + CTR caindo>20-25%`.
- **GLM-4.7-flash:** τ²-Bench 79.5 (vendor-published, tratar com cautela). Mitigação: schema-validation antes de tool call com ID.
- **LGPD/BR:** SHA-256 obrigatório sobre telefone **normalizado E.164 com 9º dígito** (número BR 8→9 dígitos quebra o match em silêncio). ANPD ativa 2025-26; base legal = legítimo interesse documentado na política de privacidade.

## 5. Brainstorm paid media — parâmetros calibrados (v1, volume baixo)

### 5.1 Motor de regras (config-driven)

| Parâmetro | v1 (volume baixo) | Afrouxar quando >50 compras/sem |
|---|---|---|
| CPL-alvo Purchase | R$40 | Ajustar por margem real |
| CPL-alvo proxy (InitiateCheckout) | R$14 (~35% Checkout→Purchase) | Substituir por Purchase direto |
| Janela mínima antes de agir | 72h | 48h |
| Gasto mínimo antes de pausa | R$60/adset (1.5× CPL) | R$80-120 |
| Pausa (composta) | CPL proxy >2× **E** freq>3.5 **E** >72h **E** gasto>R$50 | freq threshold → 4.0 |
| Escala | CPL<0.8× alvo E >72h sem edição E fora do learning | idem |
| Cadência de escala | +20%/72h | +25-30% |
| Salto de budget | >2× = duplicar adset | idem |
| Fadiga | freq>3.5 + CTR caindo>20% sem/sem | CTR>25% |
| Kill | gasto>R$120 sem conversão; máx 14d | gasto>2.5× / 10d |
| Teto por adset | R$50/dia | R$150-300/dia |
| Teto por conta | R$300/dia | R$1.000+ (migrar CBO) |

> **Racional-chave:** janela de 72h porque o ciclo de fechamento no WhatsApp dura 1-72h — CPL das primeiras 24h está subestimado (conversões ainda no chat). Nunca pausar antes de 72h, independente do CPL instantâneo.

### 5.2 Estrutura de conta ABO (consolidada, não segmentada)

```
Conta
├── Campanha 1: ToF Broad (ABO)
│   ├── Adset A: Broad interesse (mulheres 25-55 BR, saúde feminina) — R$50/dia
│   └── Adset B: Lookalike 1-3% compradores CAPI (só após 100+ purchases) — R$50/dia
└── Campanha 2: Retargeting (ABO)
    └── Adset C: conversas iniciadas sem compra (14d via BM) — R$30-50/dia
```
Budget de entrada: **R$130-150/dia**. Objetivo de campanha = **Sales** otimizando por Purchase (CAPI BM); fase de transição = Messages/Conversas até ter 50 eventos/7d. **Não** segmentar por idade/cidade/dispositivo antes de >100 conversões/adset. **Não** criar novo adset antes do existente bater 50 eventos/sem.

### 5.3 Cadência de criativo

- 3 criativos por adset (5 fragmenta sinal em volume baixo). Variável isolada por rodada, na ordem: **Hook > Formato > Ângulo > CTA**.
- Critério de decisão: gasto ≥R$60/criativo, ≥5 eventos proxy, janela ≥7d. Matar o pior, escalar o melhor, 1 variante nova/semana.
- **Score de viralização Higgsfield** (prevê CTR, não conversão): peso **50%** sem histórico → **30%** com histórico. Nunca subir criativo com hook abaixo do percentil 25 do batch.

### 5.4 Warm-up / saída do learning (sem pixel)

- **Sem 1-4:** otimizar por InitiateCheckout (proxy); consolidar em 1 adset no início pra sair do learning mais rápido; enviar também "Lead" (conversa iniciada) como sinal auxiliar.
- **Sem 5-8:** ao atingir 50 Purchase no CAPI, rodar campanha de teste otimizando por Purchase em paralelo 14d; calibrar taxa proxy→purchase.
- **Sem 9+:** migrar principal pra Purchase se >50/sem; senão manter proxy.
- **NÃO:** editar targeting em learning, pausar/reativar adset (reseta contador), trocar todos os criativos de uma vez, subir CBO antes de adsets estáveis.

### 5.5 Riscos operacionais (paid media)

1. **Undercount do `ctwa_clid`** (reaberturas/indicações não atribuem) — se >30%, guardrails matam adset bom. *[Calibração manual na Lívia → roadmap, fora desta rodada.]*
2. **Velocidade de produção criativa é o gargalo real** — fadiga em 10-14d; se Higgsfield não entregar ≥1 batch/sem, Caio roda criativo fatigado sem alternativa.
3. **Sobreposição de leilão interna** — verificar overlap (≥20% diferenciação entre adsets da mesma campanha).
4. **Retargeting** = maior ROAS potencial (INCLUÍDO na Fase 1).
5. **Compliance Meta Health/Wellness** — lista de interesses proibidos antes de configurar adset (INCLUÍDO na Fase 1).

## 6. Arquitetura técnica (@architect)

### 6.1 Handoff de criativos — DECISÃO: rclone sync cron

`inbox_poller.py` já monitora pasta local (`inbox.folder` em `settings.yaml`) com idempotência via marker `.caio_processed`. Só a origem muda.

| Opção | Verdict |
|---|---|
| A rclone FUSE mount | Rejeitar (frágil a hiccup de rede) |
| B GDrive API + service account | Aceitável (novo módulo Python) |
| C MCP GDrive | Inviável (não roda em runtime VPS) |
| **D rclone sync cron** | **RECOMENDADO** (stateless, zero código Python novo, battle-tested) |

```
[GDrive: raiz-vital/creative-inbox/] --rclone copy (systemd timer 15min)--> [VPS: /opt/caio/inbox/]
   --> inbox_poller.py (poll_once) --> MetaAdsTool.upload_creative() --> Meta Graph API
```
`rclone copy --filter "- .caio_processed"` preserva o marker local. Coexistência: operador pode continuar largando arquivo direto na pasta local.

### 6.2 Guardian + state machine

- **`agent/guardian.py`** (novo): lê `budget.max_daily_account_spend` / `max_daily_per_adset`; `check_account_hard_cap()` + `check_adset_cap()`; injetado no `OptimizeWorkflow` (padrão de `BusinessSignalReader`). Coexiste com `spend_gate.py` (SpendGate=conversacional, Guardian=autônomo — hoje ações do scheduler passam sem interceptação financeira).
- **`agent/adset_state_machine.py`** (novo): Learning→Stable→Fatiguing→Killed; mapeia o `AdSetState` já existente em `analyze.py` (hoje efêmero) para transições; persiste em Postgres `caio_adset_state` via `CAIO_DATABASE_URL`. Fallback in-memory sem DB (sem regressão).

### 6.3 Fluxo CAPI (mora 100% no zwaf)

Caio não vê lead individual (só a view agregada `caio_attribution_signal`). O zwaf já tem `ctwa_clid` (`lead_attribution.py`) e o `PAYMENT_CONFIRMED`.

```
webhook.py (captura ctwa_clid) → Lívia confirma venda → payment_gate.py
   → capi/dispatcher.py: lookup ctwa_clid por phone; hash SHA-256(E.164+9dígito);
     POST /{dataset_id}/events (Purchase, action_source=business_messaging, ph=[hash], ctwa_clid)
```
`InitiateCheckout` disparado quando o link Pix é gerado (sem esperar confirmação). Secrets `ZWAF_CAPI_DATASET_ID` / `ZWAF_CAPI_TOKEN` no zwaf (não compartilhados com Caio). Falha de CAPI **nunca** bloqueia a venda (`asyncio.create_task` isolado + retry + `capi_dispatch_log`).

### 6.4 Schema validation

**`agent/tool_validator.py`** (novo): 1 modelo Pydantic por tool mutante (`pause_ad_set`, `duplicate_ad_set`, `adjust_bid`, `create_ad`); `adset_id` deve ser string numérica pura (sem `act_`/`adset_`). `ValidationError` nunca derruba o agente — retorna erro estruturado pro LLM reformular.

### 6.5 Mapa de arquivos

**Fase 1** — Guardian + State Machine + CAPI + Schema Validation + GDrive Sync

| Arquivo | Status | Pkg |
|---|---|---|
| `agent/guardian.py` | NOVO | caio-trafego |
| `agent/adset_state_machine.py` | NOVO | caio-trafego |
| `agent/tool_validator.py` | NOVO | caio-trafego |
| `infra/gdrive-sync.service` + `.timer` | NOVO | caio-trafego |
| `src/zwaf/capi/dispatcher.py` (+`__init__`) | NOVO | zwaf |
| `agent/workflows/optimize.py` | ALTERADO | caio-trafego |
| `agent/main.py` | ALTERADO | caio-trafego |
| `agent/caio.py` | ALTERADO | caio-trafego |
| `config/settings.yaml` (seção `guardian:`) | ALTERADO | caio-trafego |
| `src/zwaf/conversion/payment_gate.py` | ALTERADO | zwaf |
| `src/zwaf/memory/lead_attribution.py` | SEM ALTERAÇÃO (já ok) | zwaf |

**Fase 2** — MoA Advisory + Retargeting + Compliance

| Arquivo | Status | Pkg |
|---|---|---|
| `agent/moa/advisor.py` | NOVO | caio-trafego |
| `agent/workflows/retargeting.py` | NOVO | caio-trafego |
| `agent/compliance/health_wellness.py` | NOVO | caio-trafego |
| `agent/llm_router.py` | ALTERADO | caio-trafego |

> Nota de faseamento: retargeting + compliance foram decididos como Fase 1 (escopo), mas a implementação de código pode entrar no fim da Fase 1 / início da Fase 2 conforme sequência das stories.

### 6.6 Riscos técnicos + rollout

1. Guardian falso positivo → `guardian.mode: warn` por 7 dias (alerta sem bloquear).
2. State machine perde estado em restart → relê do Postgres a cada ciclo; fallback in-memory.
3. CAPI falha silenciosa → retry (tenacity 3×) + `capi_dispatch_log`; nunca bloqueia venda.
4. rclone sobrescreve marker → `--filter "- .caio_processed"`.
5. Schema validation falso negativo → Pydantic `extra="allow"`, valida só obrigatórios.

**Ordem de rollout:** (1) deploy Guardian warn-only + state machine sem DB → observar 7d; (2) ligar `CAIO_DATABASE_URL` → persistência; (3) `guardian.mode: block` após validar thresholds com Fernando/Kauê; (4) CAPI dispatcher com evento sintético antes de produção; (5) rclone `--dry-run` antes do timer. Backup pré-deploy: `systemctl stop hermes` + snapshot `/opt/caio` + `pg_dump --schema-only`.

## 7. Faseamento

- **Fase 1 — Fundação (segurança + sinal real):** Guardian + hard cap · motor de regras multi-condição config-driven · state machine · CAPI (ctwa_clid + Purchase + proxy) · schema-validation · LGPD compliance · GDrive sync · retargeting estruturado · lista compliance Health/Wellness.
- **Fase 2 — Qualidade de decisão + criativo:** MoA advisory-only · creative scoring + score Higgsfield no manifest · separação Orchestrator/Executor incremental.
- **Roadmap/backlog (fora desta rodada):** calibração de undercount do `ctwa_clid` (campo manual na Lívia) · Google Search (marca+concorrentes) · migração para CBO quando volume crescer.

## 8. Respostas do dono — parâmetros v1 TRAVADOS (2026-07-04)

| # | Pergunta | Resposta | Efeito no v1 |
|---|---|---|---|
| 1 | Margem bruta/un | **Não definida** | Assume ~60% como premissa; CPL-alvo Purchase fica em R$40 (conservador). Revisar quando confirmada. |
| 2 | LTV/recompra | **Recompra frequente (60-90d)** | CAC sustentável mais alto — CPL-alvo Purchase **R$40 como piso v1**, com **stretch pra R$55-60** liberado quando a margem for confirmada. |
| 3 | Latência de fechamento | **Varia muito** | Mantém **piso de 72h** antes de pausar + janela de **atribuição 28d clique / 1d view**. |
| 4 | Cadência Higgsfield | **Indefinida** | **Risco operacional aberto.** Rotação de criativo limitada por disponibilidade: **não matar criativo sem substituto no pool**. Meta = 1 batch (3+)/sem. |
| 5 | Autonomia de escala | **Híbrido por confiança** | Escala **autônoma só em adset estável/lucrativo** (fora do learning **E** CPL<alvo por ≥7d); demais casos = **aprovação humana** no chat (timeout 2h). |
| 6 | Budget de escala | **Reinvestimento** | Teto **base R$300/dia** (retargeting incluso). Escala via reinvestimento: `teto = R$300 + 0.20 × receita_atribuída_rolling` (via CAPI). Amarra escala à venda real → **depende da story-087**. |
| 7 | Google Search 90d | **Não agora** | Removido do roadmap; foco 100% Meta/CTWA. |

### Regra de budget por reinvestimento (nova — impacta Guardian e motor de regras)
- **Teto dinâmico da conta:** `max_daily_account_spend = 300 + 0.20 × receita_atribuída_via_CAPI (janela rolling)`. Sem sinal de atribuição (CAPI ainda não maduro) → teto = R$300 fixo.
- O **Guardian (story-088)** passa a calcular o hard cap dinamicamente a partir da receita atribuída; **fail-safe:** se a leitura de receita falhar, cai no teto base R$300 (nunca acima).
- A **escala (story-090)** só reinveste os 20% em adsets que passam o gate híbrido de autonomia (estável + lucrativo ≥7d); acima disso, aprovação humana.

## 9. Quebra de stories proposta

**Fase 1**
- **S-A** CAPI Business Messaging (zwaf): `dispatcher.py` + wire `payment_gate.py` + `InitiateCheckout` proxy + LGPD hash/normalização + `capi_dispatch_log`.
- **S-B** Guardian + hard cap (caio): `guardian.py` warn-only → block, injeção no `OptimizeWorkflow`.
- **S-C** State machine de adset (caio): `adset_state_machine.py` + tabela `caio_adset_state`.
- **S-D** Motor de regras multi-condição config-driven (caio): thresholds v1 em `settings.yaml`, pausa/escala/fadiga/kill.
- **S-E** Schema validation de tool calls (caio): `tool_validator.py`.
- **S-F** GDrive handoff sync (caio/infra): `gdrive-sync.service/.timer` + runbook.
- **S-G** Retargeting estruturado (caio): `workflows/retargeting.py` + estrutura de conta ABO.
- **S-H** Lista compliance Health/Wellness (caio): `compliance/health_wellness.py`.

**Fase 2**
- **S-I** MoA advisory-only (reescopo story-085): `moa/advisor.py` + `llm_router.py`.
- **S-J** Creative scoring + score Higgsfield no manifest.
- **S-K** Separação Orchestrator/Executor (incremental).

---

*Fontes vivas: Meta CAPI for Business Messaging (developers.facebook.com), eMarketer AI media buying 2026, Gartner 2026, Madgicx/Revealbot/AdStellar, GLM-4.7-Flash benchmarks (TokenMix/DeepInfra), CAPI+LGPD BR (Produz Digital, Ancora1). Detalhe completo nos relatórios de research arquivados.*
