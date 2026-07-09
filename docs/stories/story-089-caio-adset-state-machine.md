# Story 089 — State machine de adset (persistida) [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-07) · ⚠️ migration pendente de review @data-engineer + apply na VPS

> ⚠️ **Runtime (hermes-v2-slicing §089):** wrapper Node `meta-ads-mcp-guarded/` (não `agent/adset_state_machine.py`). Estados alinhados ao slicing: LEARNING→ACTIVE→SCALING→FATIGUED→PAUSED. Reconciler é cron do Hermes (furo B): quem ESCREVE estado.

### Dev Agent Record

**File List:**
- `packages/meta-ads-mcp-guarded/src/state_machine.js` — **AC-1** lógica pura: `STATES`, `canTransition`, `canMutate` (gate: não escalar/editar budget em LEARNING; não escalar FATIGUED; PAUSED trava budget), `mapSignalToState` (**AC-2** mapeia AdSetState de analyze.py → estado, sem duplicar análise).
- `packages/meta-ads-mcp-guarded/src/state_store.js` — **AC-3/AC-5**: `PgStateBackend` (Postgres `caio_adset_state`) + `InMemoryStateBackend` (fallback sem `CAIO_DATABASE_URL`, sem regressão); `createStateStore` fábrica.
- `packages/meta-ads-mcp-guarded/src/reconciler.js` — furo B: `reconcile()` (puro) + `runReconcile()` (lê get_insights via MCP filho).
- `packages/meta-ads-mcp-guarded/src/reconcile-cron.js` — entry pro cron nativo do Hermes.
- `src/interceptors.js` — `makeStateInterceptor` (**AC-4** `get_state` + gate na pipeline, warn/enforce); `src/index.js` (store no boot); `src/config.js` (`state.mode`).
- **DB (⚠️ @data-engineer):** `packages/zwaf/infra/migrations/012_caio_adset_state.sql` (+ rollback) — tabela `adset_id PK, state CHECK, entered_at, consecutive_days, metadata JSONB`; GRANT SELECT/INSERT/UPDATE só nesta tabela ao `caio_ro`.
- `test/state.test.js` (novo).

**Completion Notes:**
- **47/47 verde** (10 state + demais + integração). Boot loga `state=warn`.
- **Verificação pendente na VPS:** caminho Postgres (`pg`) + assinatura real de `get_insights` do reconciler. Lógica pura (transições, gate, mapeamento, reconcile, store in-memory) 100% testada localmente.
- **@data-engineer:** revisar/aplicar a migration 012 antes do go-live (story sempre sinalizou envolvimento). `caio_ro` ganha escrita SÓ na `caio_adset_state`.
- Ships em `mode: warn` (gate observável antes de enforce).

**Revisão @data-engineer (Tensor) da migration 012 + ajustes de app (@developer) — 2026-07-07:**
- Migration 012 revisada: (a) coluna `consecutive_days` → **`consecutive_ticks_in_state`** (o valor conta reconfirmações do reconciler ~3x/dia, não dias de calendário; "dias no estado" = `NOW() - entered_at`); (b) índice em `state` removido (nenhuma query filtra por state; seq scan ganha nesse volume); (c) **least-privilege 2 roles**: `caio_ro` só `SELECT` (wrapper lê), novo `caio_rw` com `SELECT/INSERT/UPDATE` (reconciler escreve); COMMENTs adicionados.
- Ajustes de app pra casar: `state_store.js` (Pg+InMemory) usa `consecutive_ticks_in_state` e mantém `updated_at = NOW()` no UPDATE (zwaf não usa trigger — app mantém); `reconcile-cron.js` usa `CAIO_DB_WRITE_URL` (caio_rw) com fallback `CAIO_DATABASE_URL`; README documenta as 2 envs. Suíte **53/53 verde** após os ajustes.
- ⚠️ Deploy: `caio_rw` precisa de senha via secret (`__SET_VIA_SECRET__` no arquivo) + setar `CAIO_DB_WRITE_URL` na VPS antes de rodar o reconciler.
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §6.2
**Package:** caio-trafego

## Story Statement
**As** operador, **I want** cada adset modelado como uma máquina de estados persistida (Learning→Stable→Fatiguing→Killed), **so that** as decisões do Caio sejam auditáveis, consistentes entre ciclos e nunca ad-hoc.

## Contexto
`analyze.py` já tem `AdSetState` (CHAMPION/GOOD/ALERT/CRITICAL/INSUFFICIENT/FATIGUED) mas **efêmero** — recalculado por ciclo, sem persistência. Precisa persistir para respeitar janelas (ex: não pausar antes de 72h, não editar em learning).

## Acceptance Criteria
- **AC-1** `agent/adset_state_machine.py` com estados Learning→Stable→Fatiguing→Killed e transições disparadas por trigger.
- **AC-2** Mapeia o `AdSetState` existente de `analyze.py` para os triggers de transição (sem duplicar a lógica de análise).
- **AC-3** Persistência em Postgres `caio_adset_state` (`adset_id PK, state, entered_at, consecutive_days, metadata JSONB`) via `CAIO_DATABASE_URL`.
- **AC-4** `get_state(adset_id)` / `transition(adset_id, trigger)`; estado relido do DB no início de cada ciclo.
- **AC-5** Fallback sem DB: opera in-memory por ciclo (comportamento atual), logando warning — sem regressão.

## Escopo
- IN: state machine, migration da tabela, integração no ciclo.
- OUT: regras que consomem o estado (story-090).

## Dependências
`CAIO_DATABASE_URL` (mesmo conn de `business_signal.py`), `analyze.py`.

## Complexidade
Medium.
