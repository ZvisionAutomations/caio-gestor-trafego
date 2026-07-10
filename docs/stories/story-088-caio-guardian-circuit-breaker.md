# Story 088 — Guardian: circuit-breaker financeiro + hard cap [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-07)

> ⚠️ **Runtime (hermes-v2-slicing §1.1):** implementado no wrapper Node `packages/meta-ads-mcp-guarded/` (não `agent/guardian.py` Python legado). Intenção dos ACs preservada.

### Dev Agent Record

**File List:**
- `packages/meta-ads-mcp-guarded/src/guardian.js` — classe `Guardian`: **AC-1** teto por adset (`max_daily_per_adset`, centavos↔BRL); anti-flapping (`max_mutations_per_hour`); circuit-breaker (abre após N bloqueios, cooldown); **AC-6** `resolveAccountCap(receita)` = `base + reinvest_pct × receita` com fail-safe → base; **AC-4** modo `warn|enforce`; decision log JSONL (furo E).
- `packages/meta-ads-mcp-guarded/src/config.js` — loader do `guardrails.yaml` (artefato C) com defaults seguros e sanitização.
- `packages/caio-trafego/hermes/guardrails.yaml` — config-driven (artefato C): `guardian.mode/base_daily_cap/reinvest_pct/max_daily_per_adset/max_mutations_per_hour/circuit_breaker`. Fonte única de números (furo D).
- `src/interceptors.js` (pipeline async + plug do guardian), `src/index.js` (carrega config+guardian no boot), `test/guardian.test.js` (novo), `package.json` (dep `yaml`).

**Completion Notes:**
- **28/28 verde** (10 guardian/config + 091 + integração). Boot loga `guardian mode=warn base_cap=R$300`.
- **AC-3 (hard cap de conta bloqueia tudo) — parcial por design:** `resolveAccountCap` (a fórmula, AC-6) está testada; a checagem contra o gasto REAL da conta precisa consultar `get_insights` (assinatura da tool a confirmar na VPS) + receita atribuída (087). Per slicing, o **teto base R$300 e os checks determinísticos (adset/flapping/breaker) shipam agora**; o teto dinâmico + comparação com gasto vivo entram como sub-fase **depois de 087+089**. Wiring do `spendProvider` documentado.
- **Decision log:** escolhido **JSONL** (`GUARDED_GUARDIAN_LOG`) em vez de tabela `caio_guardian_log` — slicing (furo E) permite ambos; JSONL evita dependência de DB nesta story e já dá observabilidade do warn-mode desde o dia 1.
- **AC-5:** `spend_gate.py` (conversacional) intocado — o Guardian cobre só as tools autônomas via wrapper; coexistem.
- **Rollout:** ships em `mode: warn` (7 dias observando o decision log antes de virar `enforce`).
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §6.2
**Package:** caio-trafego

## Story Statement
**As** dono do negócio, **I want** uma camada Guardian que intercepta toda ação autônoma de gasto do Caio e impõe um teto rígido de conta, **so that** um erro do agente nunca queime budget além do limite, mesmo se a lógica de otimização falhar.

## Contexto
`spend_gate.py` intercepta só ações conversacionais (inbound WA); as ações autônomas do scheduler (ciclos morning/afternoon) passam **sem interceptação financeira**. Precisa de um guardião para ações autônomas, coexistindo com o SpendGate.

## Acceptance Criteria
- **AC-1** `agent/guardian.py` com `check_account_hard_cap(current_spend)` e `check_adset_cap(adset_id)` lendo `budget.max_daily_account_spend` (R$300) e `max_daily_per_adset` (R$50) de `settings.yaml`.
- **AC-2** Injetado no `OptimizeWorkflow` (padrão de `BusinessSignalReader`); toda ação de pause/bid/duplicate passa pelo Guardian.
- **AC-3** Ao atingir o hard cap da conta: bloqueia TODAS as ações do ciclo e alerta no WhatsApp/Telegram.
- **AC-4** Flag `guardian.mode: warn|block` em `settings.yaml`; default **warn** (alerta sem bloquear) por 7 dias antes de `block`.
- **AC-5** Não substitui `spend_gate.py` (coexistem: SpendGate=conversacional, Guardian=autônomo).
- **AC-6** **Teto dinâmico por reinvestimento:** `max_daily_account_spend = 300 + 0.20 × receita_atribuída_via_CAPI (rolling)`. **Fail-safe:** se a leitura de receita atribuída falhar ou o CAPI ainda não estiver maduro, cai no teto base **R$300 fixo** (nunca acima). Config: `guardian.reinvest_pct: 0.20`, `guardian.base_daily_cap: 300`.

## Escopo
- IN: guardian.py, injeção no OptimizeWorkflow, seção `guardian:` no settings.yaml, modo warn/block.
- OUT: state machine (story-089), regras de otimização (story-090).

## Dependências
`settings.yaml` (budget já existe), `MetaAdsTool.get_account_spend`.

## Complexidade
Medium.
