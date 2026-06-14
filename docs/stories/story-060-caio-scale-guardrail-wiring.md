# Story 060 — Conectar a trava de escala (business signal) ao ciclo de otimização

**Status:** Done
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Track:** Standard
**Owner sugerido:** @developer (Pixel)
**Criada por:** @sprint-lead (Sync) — 2026-06-14
**Validada por:** @product-lead (Axis) — 2026-06-14 — GO
**Implementada/QA:** @developer + @quality-gate — 2026-06-14 — QA Gate PASS (`docs/qa/gates/story-060-gate.yaml`)

### Dev Agent Record (File List)
- `agent/workflows/optimize.py` (reader+tetos no __init__; _read_signal fail-safe sync; _scale_decision; gate na ação duplicate_ad_set → ActionLog BLOQUEADO)
- `agent/main.py` (_load_settings_section genérico; injeta BusinessSignalReader + tetos do budget no OptimizeWorkflow)
- `harnesses/test_scale_guardrail.py` (novo) + `scripts/run_harnesses.py`
QA: 14/14 harnesses, ruff/mypy limpos. Default bloqueia (sem reader/DB/erro → escala travada). CodeRabbit WAIVED.

---

## Story Statement
**As** operador da Raiz Vital,
**I want** que a duplicação autônoma de ad set do Caio seja **bloqueada** quando não houver venda paga atribuída no período E tetos de escala definidos,
**so that** o Caio nunca escale gasto em produção sem sinal de negócio real — a trava de segurança que a story-039 projetou mas que nunca foi ligada.

## Contexto (verificado no código)
- `agent/business_signal.py` tem `BusinessSignalReader.get_adset_signal()` e `evaluate_scale_guardrails(...)` — testados isoladamente (`test_business_signal_blocks_scale_without_guardrails_or_paid_sale`).
- **MAS** `agent/workflows/optimize.py` executa `duplicate_ad_set` (`_execute_autonomous_actions`, ~linha 148) **sem consultar** nenhum dos dois. Os tetos em `settings.yaml` (`budget.max_new_adsets_per_day`, `max_duplications_per_adset_per_day`, `min_business_signal_to_duplicate`) são **decorativos** hoje.
- Defaults seguros já existem no settings (tetos = 0 → escala bloqueada). Falta só **enforçar**.

## Acceptance Criteria (Given/When/Then)
**AC-1 — Duplicação autônoma exige sinal + tetos**
- **Given** uma ação autônoma `duplicate_ad_set` recomendada,
- **When** o `OptimizeWorkflow` vai executá-la,
- **Then** ele consulta o `BusinessSignalReader` + `evaluate_scale_guardrails`; só chama `self.meta.duplicate_ad_set` se `decision.allowed` for True (tetos > 0 **e** venda paga atribuída no período).

**AC-2 — Bloqueio é seguro e registrado**
- **Given** sinal ausente OU tetos = 0,
- **When** a duplicação é avaliada,
- **Then** a API Meta **não** é chamada; um `ActionLog` "DUPLICAÇÃO BLOQUEADA — guardrail" é registrado com o motivo; o ciclo segue sem erro.

**AC-3 — Fail-safe (sem DB / erro do reader)**
- **Given** `CAIO_DATABASE_URL` ausente ou erro ao ler o sinal,
- **When** a duplicação é avaliada,
- **Then** o resultado é **bloquear** (lado seguro) — nunca escalar por engano; nunca derrubar o ciclo.

**AC-4 — Demais ações inalteradas**
- **Given** ações `pause_ad_set`/`pause_creative`/`adjust_bid` e o fluxo de aprovação (`duplicate_ad_set_budget_exceeded`),
- **When** o ciclo roda,
- **Then** comportam-se como antes (sem regressão).

**AC-5 — Harness/testes verdes**
- **Then** novo teste cobre: bloqueio sem sinal/tetos; liberação com venda paga + tetos > 0; fail-safe sem reader. Suíte verde, ruff + mypy limpos.

## Escopo
### IN
- `OptimizeWorkflow.__init__` aceita `business_signal_reader` + limites de escala + `tenant_id`/`signal_days` (defaults seguros do settings).
- Wrapper sync p/ ler o sinal async (fail-safe → sinal vazio em erro).
- Gate na ação `duplicate_ad_set`.
- Wiring no `main.py` (injeta reader + tetos do settings).
- Harness novo.
### OUT
- Credenciais Meta / `CAIO_DATABASE_URL` real (a trava funciona sem — bloqueando).
- Mudar a lógica de análise (analyze.py) — só o enforcement no optimize.

## Dependências
- Reusa `business_signal.py` (story-039). Sem dependência externa.

## QA
- Tipo: Feature/Safety. Foco: defesa em profundidade, fail-safe, sem regressão. CodeRabbit WAIVED se não provisionado.
