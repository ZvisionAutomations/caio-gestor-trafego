# Story 058 — Campaign Inbox no ciclo automático do scheduler

**Status:** Done
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Track:** Standard
**Owner sugerido:** @developer (Pixel)
**Criada por:** @sprint-lead (Sync) — 2026-06-14
**Validada por:** @product-lead (Axis) — 2026-06-14 — GO
**Implementada/QA:** @developer + @quality-gate — 2026-06-14 — QA Gate PASS (`docs/qa/gates/story-058-gate.yaml`)

### Dev Agent Record (File List)
- `agent/inbox_poller.py` (novo — discover/mark/poll_once idempotente + fail-safe)
- `agent/tools/scheduler.py` (register_inbox_poll, IntervalTrigger)
- `agent/main.py` (_load_inbox_settings + inbox_cycle + registro condicional)
- `config/settings.yaml` (bloco `inbox`: enabled/poll_minutes/folder/dry_run)
- `harnesses/test_inbox_poller.py` (novo) + `scripts/run_harnesses.py` (registro)
QA: 13/13 harnesses, ruff/mypy limpos. Idempotência por marcador `.caio_processed` (só marca `uploaded_paused`). Dry-run default seguro. CodeRabbit WAIVED.

---

## Story Statement

**As** operador da Raiz Vital,
**I want** que o Caio processe automaticamente novos pacotes de campanha depositados na pasta de handoff (sem rodar um comando manual),
**so that** os criativos preparados (Higgsfield → pasta) virem campanhas PAUSED na Meta sem intervenção, no fluxo "deposita → Caio sobe".

---

## Contexto (verificado no código)
- `agent/tools/scheduler.py` registra apenas 4 jobs: `register_morning_analysis` (08h), `register_afternoon_check` (14h), `register_daily_report` (20h30), `register_threshold_recalibration`. **Não há job de inbox.**
- O Campaign Inbox roda **só via** `scripts/process_campaign_inbox.py` (CLI manual, uma pasta por execução), usando `agent/workflows/campaign_inbox.py` (`CampaignInboxWorkflow`).
- O CLI já tem modo `--dry-run` com `_DryRunMeta`/`_DryRunWhatsApp`.
- `main.py` monta os ciclos do scheduler, mas não inclui o inbox.
- Decisão de escopo (memória `caio-gestor-trafego-escopo`): fluxo "Higgsfield gera → usuário deposita na pasta → Caio sobe".

## Dependência crítica
- **Upload real (PAUSED) precisa das credenciais Meta do Fernando** → sem elas, **só dry-run**. Esta story é **construível e testável agora em dry-run** (mocks), com flag explícita dry-run vs real. Go-live real fica atrás do gate do Fernando.

---

## Acceptance Criteria (Given/When/Then)

**AC-1 — Job de inbox registrado no scheduler**
- **Given** o Caio inicia (`main.py`),
- **When** o scheduler é montado,
- **Then** existe um job recorrente de inbox (ex.: `register_inbox_poll`, intervalo configurável em `settings.yaml`, ex. a cada 15 min) registrado junto dos demais ciclos, com `misfire_grace_time` e log da próxima execução.

**AC-2 — Polling processa pacotes novos**
- **Given** uma pasta de handoff (raiz configurável em `settings.yaml`) com 1+ subpastas contendo `manifest.yaml` válido,
- **When** o job de inbox roda,
- **Then** cada pacote novo é processado via `CampaignInboxWorkflow.process_folder` (upload PAUSED no modo real, ou dry-run conforme flag).

**AC-3 — Idempotência (não reprocessar)**
- **Given** uma pasta já processada com sucesso,
- **When** o job roda de novo,
- **Then** ela **não** é reprocessada (marcação durável: mover p/ subpasta `processed/` OU arquivo-marcador `.caio_processed` OU registro append-only). Sem upload duplicado na Meta.

**AC-4 — Fail-safe por pacote**
- **Given** um pacote inválido/erro de upload,
- **When** o job processa o lote,
- **Then** o erro daquele pacote é registrado (e notificado via WhatsApp, padrão dos outros ciclos) e **não derruba** o job nem impede os demais pacotes; pacote com erro não é marcado como processado (permite retry).

**AC-5 — Flag dry-run vs real**
- **Given** `settings.yaml` (ou env),
- **When** o job é construído,
- **Then** há flag explícita (ex.: `inbox.dry_run`) que escolhe `MetaAdsTool` real vs dry-run; default seguro documentado. Sem credenciais Meta, dry-run não quebra.

**AC-6 — Harness/testes verdes**
- **Given** a suíte de harnesses,
- **When** executada,
- **Then** novo harness cobre: registro do job, processamento de pasta nova (dry-run), idempotência (pasta processada ignorada), fail-safe (pacote inválido não derruba lote). ruff + mypy limpos; sem regressão.

---

## Escopo
### IN
- Novo método no `CaioScheduler` (ex.: `register_inbox_poll`) + `CronTrigger`/`IntervalTrigger`.
- Loop de polling idempotente sobre a pasta de handoff (descoberta de subpastas + marcação de processados).
- Wiring no `main.py` (registrar o ciclo de inbox).
- Flag dry-run vs real em `settings.yaml` + chave de intervalo + raiz da pasta.
- Harness novo + ajustes mínimos.

### OUT
- Credenciais Meta Ads (Fernando) — só dry-run sem elas.
- Deploy do agente Caio na VPS (story separada).
- Mudança no schema do manifest (isso é a story-059).
- Lógica de carrossel (story-059).

---

## Dependências
- **Não-bloqueante p/ construir:** credenciais Meta (só p/ go-live real).
- Reusa `CampaignInboxWorkflow` (story-039, já mergeada) — sem reescrever o parser/translate.

## Notas técnicas (dev)
- APScheduler já em uso (`BlockingScheduler`); usar `IntervalTrigger` (minutes) ou `CronTrigger`.
- Idempotência durável é o ponto mais sensível — escolher 1 mecanismo e cobrir com teste explícito.
- Estação Windows sem Python → harnesses no WSL (`wsl -u root`, `mount -t drvfs G: /mnt/g`).

## CodeRabbit / QA
- Tipo: Feature. Foco: idempotência, fail-safe, ausência de upload duplicado. CodeRabbit WAIVED se não provisionado.

## Test Strategy
- Unit/harness: registro do job; processa pasta nova (dry-run); idempotência; fail-safe por pacote. Smoke offline sem credenciais.
