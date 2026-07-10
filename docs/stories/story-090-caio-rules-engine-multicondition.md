# Story 090 — Motor de regras multi-condição (config-driven) [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-07) · receita ao vivo pendente de 087

> ⚠️ **Runtime (hermes-v2-slicing §090):** thresholds no `guardrails.yaml` (config C) + avaliador determinístico no wrapper Node (não `optimize.py`). Raciocínio "qual regra dispara" é SOUL; enforcement é Guardian(088)+state(089), já construídos.

### Dev Agent Record

**File List:**
- `packages/meta-ads-mcp-guarded/src/rules.js` — `evaluateAdset(m, state, cfg)`: **AC-2** pausa composta (CPL proxy>2× E freq>3.5 E >72h E gasto>R$50 — nunca métrica única); **AC-3** escala (CPL<0.8×alvo E >72h sem edição E fora do learning; salto>2×→duplicar); **AC-3.1** autonomia híbrida (autônomo só fora do learning E ≥7d lucrativo); **AC-5** fadiga (freq+CTR↓20%) e kill (gasto>R$120 sem conversão / 14d); **AC-4** não escala em LEARNING (consome 089). `reinvestBudget()` = **AC-3.2** base + 0.20×receita (fail-safe → base).
- `packages/caio-trafego/hermes/guardrails.yaml` — seção `rules:` (**AC-1** todos os thresholds tunáveis sem redeploy) + `state:`.
- `src/config.js` — defaults + merge de `rules`/`state`.
- `test/rules.test.js` (novo, 10 casos).

**Completion Notes:**
- **53/53 verde.** Avaliador determinístico é a fonte do "o que fazer"; a execução é o Hermes (SOUL) chamando a tool, **AC-6** sempre gated pelo Guardian (088) + state (089) — já integrados na pipeline.
- **Pendente (dep 087):** o feed de `receita_atribuída_via_CAPI` que alimenta `reinvestBudget`/teto dinâmico do Guardian. A fórmula está testada; o valor vivo vem do DB quando a 087 (CAPI) rodar. Sem sinal → sem reinvest (só teto base), por design.
- **SOUL:** falta uma diretiva curta no `SOUL-v2.md` referenciando as regras/limites do config (single source of truth — o SOUL não reescreve número). Anotado como ajuste de prompt no deploy.
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §5.1, §6.2
**Package:** caio-trafego

## Story Statement
**As** gestor de tráfego, **I want** que as decisões de pausa/escala/fadiga/kill do Caio usem regras multi-condição com thresholds em config, **so that** ele pare de pausar por CPL isolado (matando adset em learning) e eu possa afinar os números sem redeploy.

## Contexto
Hoje pausa por CPL isolado. Research 2026: nunca agir por métrica única; respeitar janela de 72h (ciclo de fechamento no WhatsApp) e learning phase.

## Acceptance Criteria
- **AC-1** Todos os thresholds em `settings.yaml` (tunáveis sem redeploy): CPL-alvo Purchase R$40, CPL proxy R$14, janela mín 72h, gasto mín R$60, freq 3.5, escala +20%/72h, fadiga CTR↓20%, kill R$120/14d, tetos R$50/R$300.
- **AC-2** **Pausa composta:** `CPL proxy >2× E freq>3.5 E rodando>72h E gasto>R$50`.
- **AC-3** **Escala:** `CPL<0.8× alvo E >72h sem edição E fora do learning`; +20%/72h; salto >2× = **duplicar** adset (não editar).
- **AC-3.1** **Autonomia híbrida:** escala **autônoma** só em adset estável/lucrativo (fora do learning **E** CPL<alvo por ≥7d consecutivos); demais casos = **aprovação humana** no chat (timeout 2h).
- **AC-3.2** **Escala por reinvestimento:** o incremento de budget é financiado por `0.20 × receita_atribuída_via_CAPI`; respeita o teto dinâmico do Guardian (story-088 AC-6). Sem sinal de atribuição → sem reinvestimento (só teto base).
- **AC-4** **Não editar durante learning** (50 eventos/7d); consome o estado da story-089.
- **AC-5** **Fadiga:** `freq>3.5 + CTR caindo>20% sem/sem` → sinaliza nova variante. **Kill:** gasto>R$120 sem conversão, máx 14d.
- **AC-6** Toda ação passa pelo Guardian (story-088) antes de executar.

## Escopo
- IN: regras multi-condição em `optimize.py`, config de thresholds.
- OUT: Guardian (088), state machine (089) — consumidos aqui.

## Dependências
story-088 (Guardian), story-089 (state machine), story-087 (sinal Purchase/proxy p/ CPL real).

## Complexidade
Medium-Heavy.
