# Re-fatiamento Arquitetural — Stories v2 no Runtime Hermes

> **@architect (in-thread, 2026-07-05).** Torna as 8 stories da Fase 1 developer-ready no runtime REAL (Hermes v0.18 = SOUL + MCP), não no `agent/` Python legado.
> **As ACs (o QUE) não mudam** — muda o ONDE o código vive. Fonte da decisão de runtime: `runbooks/runtime-reconciliation-decision.md`. Doc mestre: `caio-v2-upgrade-master.md`.

---

## 0. Princípio de fatiamento (por que colapsa em wrapper + SOUL + config)

O Hermes é um LLM governado por prompt (`SOUL.md`) + tools de um MCP (`meta-ads-mcp`). Ele **não é código Python nosso**. Então:

| Tipo de lógica | Onde vive no Hermes | Por quê |
|---|---|---|
| Raciocínio, priorização, "quando escalar" | **SOUL-v2.md** (prompt) | É julgamento — é pra isso que o LLM serve |
| **Enforcement determinístico** (teto R$, `adset_id` válido, circuit-breaker, lista de compliance) | **Wrapper do `meta-ads-mcp`** (intercepta a tool antes da Graph API) | LLM NÃO é determinístico. Guardrail que pode falhar não é guardrail. |
| Thresholds / listas / flags | **`config.yaml`** lido pelo wrapper | Config-driven (resposta do dono §8) — muda sem redeploy |
| Estado persistido (adset state, receita atribuída) | **DB sidecar** (`caio_adset_state`, lido pelo wrapper + CAPI) | Precisa sobreviver a restart e ser fonte única |

**Consequência:** 5 das 8 stories (088/089/090/091/094) **colapsam em UM artefato de engenharia** — o `meta-ads-mcp-guarded` (proxy, §1.1) — mais diretivas no SOUL e chaves no config. Não são 5 módulos Python soltos.

> **Regra de single source of truth (furo D):** todo NÚMERO/limite/lista vive **só** no `config.yaml`. O `SOUL-v2.md` **nunca reescreve valores** — apenas os referencia ("respeite os limites impostos pelo guardian; não escale adset instável"). Isso evita divergência (SOUL dizer R$X e o config enforcar R$Y). O enforcement determinístico é sempre a fonte; o SOUL é orientação em linguagem natural que aponta pra ele.

---

## 1. Os 4 artefatos-alvo da Fase 1 (o "onde")

| # | Artefato | Natureza | Repo/Local | Absorve as stories |
|---|---|---|---|---|
| **A** | `meta-ads-mcp-guarded` | **Proxy MCP** (NÃO fork) que intercepta tools mutantes (`create_ad`, `update_adset`, `update_campaign`, `upload_ad_image`, …) | novo pkg `packages/meta-ads-mcp-guarded/` (Node) — ver §1.1 | 088, 089(enforce), 090(enforce), 091, 092b, 094(enforce) |
| **B** | `SOUL-v2.md` | Prompt de governança do Caio (estende o `hermes/SOUL.md` atual) | `packages/caio-trafego/hermes/SOUL-v2.md` | 088(soft), 089(transições), 090(raciocínio), 093, 094(soft) |
| **C** | `config.yaml` | Thresholds, listas, flags, caps | `packages/caio-trafego/hermes/config.yaml` (lido pelo wrapper A) | 088, 090, 094 + flags de rollout |
| **D** | DB sidecar | Tabelas `caio_adset_state` (+ **reconciler** cron que a escreve), `caio_guardian_log` (decision log 088), `caio_upload_ledger` (idempotência 092b) + leitura de receita atribuída (via 087/CAPI) | `CAIO_DATABASE_URL` (migration) | 089, 090(reinvest), 088(log), 092b(ledger), 087(consome) |

+ **Track zwaf independente:** story-087 (CAPI) segue como escrita, do lado da Lívia. É pré-requisito de 090/093 (sem atribuição não há reinvestimento).

### 1.1 Artefato A é PROXY, não fork (decisão de manutenção)

**Não forkar** o `meta-ads-mcp` (é 3rd-party, roda via `npx`; forkar = herdar merge de todo update upstream). Em vez disso:

- `meta-ads-mcp-guarded` é um **MCP server próprio** que o Hermes aponta **no lugar** do `meta-ads-mcp`.
- Internamente ele **spawna o `meta-ads-mcp` real como processo filho** (stdio) e faz **passthrough** de todas as tools.
- Só as **tools mutantes** (`create_ad`, `update_adset`, `update_campaign`, `upload_ad_image`, `create_adset`, `create_campaign`, `update_ad`, `create_ad_creative`) passam pelos **interceptors** (validação 091 → guardian 088 → compliance 094 → state 089) ANTES de repassar ao filho. As read-only (`get_*`, `search_*`, `get_insights`) passam direto.
- **Config Hermes:** trocar o endpoint do MCP `meta-ads` → `meta-ads-mcp-guarded`. Upstream continua intacto e atualizável (`npx meta-ads-mcp` como dependência interna).
- **Vantagem:** zero divergência de upstream; a superfície de tools espelha 1:1 automaticamente (passthrough), só adicionamos o `upload_creative_from_inbox` (092b) como tool nova.

---

## 2. Re-fatiamento story por story

### 087 — CAPI Business Messaging → **NÃO MUDA**
- Vive em `zwaf/capi/` (lado Lívia). Independe do runtime do Caio.
- Papel v2: **foundation**. Emite `Purchase` (business_messaging) → alimenta o DB sidecar (D) com receita atribuída → habilita reinvestimento (090) e retargeting (093).
- Bloqueio externo: credenciais Meta (dataset + token) + confirmar WABA. → **mensagem pro Cauê** (`runbooks/mensagem-caue-meta-credentials.md`).

### 088 — Guardian / circuit-breaker → **Wrapper (A) + config (C) + SOUL (B)**
- **Determinístico no wrapper A:** antes de QUALQUER tool que gaste (`update_adset` budget, `create_ad`, `update_campaign`), o wrapper lê `config.yaml` e BLOQUEIA se: `daily_account_spend > cap` | mais de N pausas/ativações na janela (anti-flapping) | teto dinâmico `300 + 0.20 × receita_atribuída` estourado.
- **Config C:** `guardian.base_daily_cap: 300`, `guardian.reinvest_pct: 0.20`, `guardian.max_mutations_per_hour`, `guardian.circuit_breaker.*`.
- **SOUL B:** diretiva soft "não escale adset instável; explique no Telegram antes de agir".
- **Decision log (NOVO — furo E):** o wrapper escreve um log estruturado de TODA decisão de interceptor (`{timestamp, tool, args_resumidos, verdict: allow|block, rule, valor, would_block}`) desde o dia 1 — em `caio_guardian_log` (DB) ou JSONL em `/var/log/caio-guardian.log`. **Sem isso o warn-mode é cego** (não dá pra saber o que ELE teria bloqueado). Serve de base pra decidir a virada warn→enforce.
- **Rollout:** flag `guardian.mode: warn|enforce` → 7 dias em `warn` (em warn, `verdict=allow` + `would_block=true` no log, não bloqueia). Teto **base R$300** roda standalone; o teto **dinâmico** (`300 + 0,20×receita`) só entra como sub-fase **depois de 087+089** (antes disso não há receita atribuída pra computar).

### 089 — State machine de adset → **DB sidecar (D) + reconciler + wrapper (A) + SOUL (B)**
- **DB D:** migration `caio_adset_state` (adset_id, state, since, last_transition, reason). Envolver **@data-engineer**.
- **Reconciler (NOVO — furo B):** as transições reais são **dirigidas por leitura de insight**, não por mutação (um adset SAI de learning por tempo/eventos; FADIGA por freq>3.5 + CTR↓ — nada disso é uma tool call nossa). Um **cron nativo do Hermes** (junto do ciclo 08/14/20:30) lê `get_insights` e **escreve** as transições temporais/métricas em `caio_adset_state`. **Quem escreve estado = reconciler.**
- **Wrapper A:** só **LÊ** `caio_adset_state` pra decidir se permite a mutação (ex.: bloquear SCALING em adset LEARNING); expõe `get_adset_state` read-only pro Hermes. O wrapper só grava a transição *causada por uma mutação* (ex.: PAUSED após pause); as temporais/métricas são do reconciler.
- **SOUL B:** define as transições permitidas (LEARNING→ACTIVE→SCALING→FATIGUED→PAUSED) e o que o Caio faz em cada uma.

### 090 — Motor de regras multi-condição → **SOUL (B) + config (C) + wrapper (A) + DB (D)**
- **Config C:** as regras viram YAML (`rules[]` com condição→ação), config-driven (resposta do dono).
- **SOUL B:** raciocínio "qual regra dispara agora, dado o insight". Autonomia híbrida: **age sozinho só se** adset fora de learning **E** CPL<alvo por ≥7d (senão sugere no Telegram).
- **Wrapper A:** enforce da ação (respeita 088).
- **DB D:** escala por reinvestimento = `novo_teto = 300 + 0.20 × receita_atribuída` (receita vem de 087).
- Depende de 087 + 088 + 089.

### 091 — Schema validation de tool calls → **Wrapper (A)**
- **Wrapper A:** valida args ANTES do dispatch — `adset_id`/`campaign_id`/`ad_id` batem `^\d+$`, budgets em centavos e >0, enums válidos. Se inválido → rejeita com erro claro (não chama a Graph API com lixo que o LLM alucinou).
- É a defesa anti-alucinação do runtime. Barato, alto valor. Pode ser o **primeiro** a codar (fundação do wrapper A).

### 092 — GDrive handoff → **SPLIT em 092a (infra) + 092b (upload tool)** ⬇ ver §3

### 093 — Retargeting estruturado → **SOUL (B) + MCP**
- **SOUL B:** diretiva de estrutura de retargeting (públicos: engajou WhatsApp, iniciou checkout sem comprar via 087, LAL de compradores).
- Usa tools do MCP (`create_adset` com custom audience). Depende de 087 (sinal) + 090 (regras).

### 094 — Compliance Health/Wellness → **config (C) + wrapper (A) + SOUL (B)**
- **Config C:** lista de termos proibidos/claims regulados (ANVISA/Meta health policy).
- **Wrapper A:** ao criar/editar criativo/copy via tool, faz match contra a lista → bloqueia/avisa (`compliance.mode: warn|enforce`).
- **SOUL B:** guardrail soft "não prometa cura, não use antes/depois clínico".

---

## 3. DECISÃO FECHADA — 092 upload (o gap do Hermes)

**Problema:** a 092 original assume `inbox_poller.py` (Python legado) que monitora a pasta local, lê o manifest e sobe. **O Hermes não herda isso.** rclone põe os arquivos na VPS, mas nada consome.

**Decisão: 092 vira duas stories.**

### 092a — rclone sync (infra) → **segue como a story atual**
- systemd service+timer, `rclone copy gdrive:raiz-vital/creative-inbox /opt/caio/inbox --filter "- .caio_processed"`, 15 min. readonly. Runbook pronto (`gdrive-rclone-handoff-setup.md`). Conta `zvisionforb2b` (decidido).
- Entrega: os criativos + `manifest.yaml` chegam na VPS. **Fim do escopo da 092a.**

### 092b — `upload_creative_from_inbox` (tool MCP custom) → **NOVA, no wrapper (A)** ✅ escolhida
Comparação:

| Opção | Determinismo | Idempotência | Risco | Veredito |
|---|---|---|---|---|
| **Tool MCP custom** (escolhida) | ✅ código | ✅ escreve `.caio_processed` após sucesso | baixo | **VENCE** |
| Cron-prompt (LLM lê pasta e sobe) | ❌ LLM parseia manifest/decide | ❌ risco de subir 2x | double-spend, alucinação | rejeitada |

**Spec da tool `upload_creative_from_inbox` (no `meta-ads-mcp-guarded`, artefato A):**
- **Input:** opcional `campaign_folder` (default: varre `/opt/caio/inbox/*` sem `.caio_processed`).
- **Passos determinísticos:**
  1. Lista subpastas sem marker `.caio_processed`.
  2. Lê + valida `manifest.yaml` (schema: campaign, creative.type, copy, destination, budget). Inválido → pula + reporta, não sobe.
  3. Chama a cadeia do MCP: `upload_ad_image`/`get_ad_video` → `create_ad_creative` → `create_ad` (no adset/campanha do manifest). Passa pelos guardrails 088/091/094 do próprio wrapper.
  4. **Idempotência por LEDGER, não por marker grosso (furo C):** o upload é multi-passo — se falhar no meio (creative criado, ad não), re-run com marker simples **duplicaria o creative**. Manter um **ledger** (`caio_upload_ledger`: `manifest_hash`, `step`, `meta_id`, `status`) keyed por **hash do manifest + assets**. Cada sub-passo grava o ID Meta retornado. Retry **retoma do passo pendente** (reusa image_hash/creative_id já criados), nunca reinicia do zero. O `.caio_processed` só é escrito **após o `create_ad` final** confirmar — é o commit da "transação".
  5. Retorna resumo (subiu X, pulou Y, erro Z, retomou W) → Hermes avisa no Telegram.
- **Invocação:** cron nativo do Hermes chama a tool (ex.: junto do ciclo 08:30) OU sob comando "sobe os criativos novos". O LLM **não parseia o manifest** — só chama a tool e relata o retorno.
- **Depende de:** 092a (arquivos na VPS) + wrapper A existir (091 primeiro).
- **⚠️ AC obrigatório quando esta virar story formal (herdado de story-095, 2026-07-07):** a tool DEVE usar `page_id`/`whatsapp_phone_number` do `manifest.yaml` **de cada pacote/campanha individualmente** (schema já existe em `agent/campaign_inbox.py::CampaignSpec`) — nunca um valor único hardcoded/global. Isso é o que permite rodar múltiplos produtos (ex.: AlphaPulse → número do Fernando, New Woman → número da Lívia) em paralelo sem misturar destino de clique. @sprint-lead: incluir como AC formal ao rascunhar a story 092b.

---

## 4. Ordem de implementação re-fatiada

```
091 (funda o wrapper A: proxy + validação de schema)
  → 088 (Guardian no wrapper A + config C + caio_guardian_log; ships warn-only, teto base R$300)
      ↳ migration DB sidecar D começa aqui (@data-engineer): caio_guardian_log
  → 089 (estende D: caio_adset_state + RECONCILER cron; state read no wrapper)
  → 087 (CAPI zwaf — foundation de atribuição; paralelo, mas bloqueia 090/093 e o teto dinâmico de 088)
  → 090 (regras: SOUL B + config C + reinvest via D; libera teto dinâmico do 088)
  → 092a (rclone infra) → 092b (tool upload no wrapper A + caio_upload_ledger)
  → 094 (compliance no wrapper A + config C)
  → 093 (retargeting: SOUL B, consome 087)
```
Racional: 091 primeiro porque **cria o proxy A** onde 088/092b/094 vão morar. A **migration do DB sidecar D** é prereq compartilhado — nasce na 088 (`caio_guardian_log`), estende na 089 (`caio_adset_state`) e 092b (`caio_upload_ledger`); envolver **@data-engineer** desde a 088. 087 corre em paralelo (track zwaf) mas trava 090/093 **e** a sub-fase de teto dinâmico do 088.

## 5. De-para de rollout (flags viram config do wrapper, não settings.yaml Python)

| Componente | Flag (em `config.yaml`) | Default no rollout |
|---|---|---|
| Guardian | `guardian.mode` | `warn` (7d) → `enforce` |
| Compliance | `compliance.mode` | `warn` → `enforce` |
| Regras autônomas | `rules.autonomy` | `suggest` (Telegram) → `hybrid` |
| Upload tool | `upload.enabled` | `false` até 092a validado |

## 6. O que continua valendo (sem retrabalho)
- Todas as ACs de negócio + thresholds v1 (§8 do doc mestre).
- story-087 inteira (CAPI zwaf).
- Os 3 runbooks de pré-deploy.
- A pasta `creative-inbox` + `manifest.yaml` já criados.
- **@product-lead** re-valida só o *onde* (as ACs não mudaram) → mantém Ready.

---

## 7. Registro de revisão arquitetural (@architect / Stratum — 2026-07-05)

Revisão do split → **5 furos corrigidos** (dobrados neste doc):
| Furo | Correção aplicada | Seção |
|---|---|---|
| **A** Fork herda manutenção upstream | Vira **proxy MCP** (spawna meta-ads-mcp real como filho, passthrough + interceptors só nas mutantes) | §1.1 |
| **B** State machine perde transições temporais/métricas (não-mutação) | **Reconciler** cron lê insights e escreve `caio_adset_state`; wrapper só lê | §2 (089) |
| **C** Idempotência grossa duplica creative em falha parcial | **Ledger** `caio_upload_ledger` por hash+step; retoma do passo pendente | §3 (092b) |
| **D** SOUL e config podem divergir em números | **Single source of truth:** números só no config; SOUL referencia | §0 |
| **E** Warn-mode cego sem registrar o que bloquearia | **Decision log** `caio_guardian_log` desde dia 1 | §2 (088) |

Impacto no plano: +1 cron (reconciler, dentro da 089), +2 tabelas (`caio_guardian_log`, `caio_upload_ledger`), migration do DB sidecar antecipada pra 088. Ordem e ACs de negócio inalteradas. **Veredito: split APROVADO com as correções acima — developer-ready.**
