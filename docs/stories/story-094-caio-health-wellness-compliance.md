# Story 094 — Lista de compliance Health/Wellness [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-07)

> ⚠️ **Runtime (hermes-v2-slicing §1.1):** implementado como interceptor no wrapper Node `packages/meta-ads-mcp-guarded/` (não `agent/compliance/health_wellness.py` Python legado).

### Dev Agent Record

**File List:**
- `packages/meta-ads-mcp-guarded/src/compliance.js` — classe `Compliance`: **AC-2** deep-scan de TODA string dos args (copy + targeting) contra termos proibidos + claim patterns; **AC-4** fail-closed (matching normaliza acento/caixa, casa por palavra `\b`); modo `warn|enforce` (ships warn); decision log JSONL.
- `packages/caio-trafego/hermes/guardrails.yaml` — seção `compliance:` (**AC-1/AC-3** lista baseline de termos Health/Wellness + claim patterns, editável sem redeploy).
- `src/config.js` (defaults + merge da seção compliance), `src/index.js` (instancia Compliance, pluga na pipeline após o guardian — ordem do slicing), `test/compliance.test.js` (novo).

**Completion Notes:**
- **37/37 verde** (9 compliance + 10 guardian/config + 091 + 4 integração). Boot loga `compliance mode=warn (16 termos)`.
- **AC-3 (lista vs docs Meta) — parcial e honesto:** a lista é um **baseline** rastreável à política Personal Health/sensitive-categories da Meta, marcado no YAML como "revisar periodicamente, não é parecer jurídico". Revisão legal externa é OUT (escopo da story). Editável sem redeploy.
- **AC-4 fail-closed:** matching agressivo por palavra normalizada; exceção de infra ainda é fail-open (não derruba o agente) — só o *match* erra pro lado de bloquear.
- Falso-positivo por substring evitado (`\b`): "curadoria" não dispara "cura".
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §5.5 (Risco 5)
**Package:** caio-trafego

## Story Statement
**As** dono do negócio, **I want** que o Caio conheça e respeite as restrições da Meta para Health/Wellness antes de configurar qualquer adset, **so that** a conta não seja restrita/banida por violação de política (o que paralisaria toda a operação).

## Contexto
Suplemento feminino é categoria sensível. A Meta restringe targeting por termos ligados a condições de saúde (menopausa, hormônios, fertilidade). Uma restrição de conta paralisa a operação — é barreira de risco alto.

## Acceptance Criteria
- **AC-1** `agent/compliance/health_wellness.py` com lista de interesses/termos **proibidos** e regras de linguagem (ex: sem afirmação de "antes/depois" pessoal, sem alvo por condição de saúde).
- **AC-2** Toda configuração de targeting/criativo do Caio é validada contra a lista antes do upload; violação = bloqueia + alerta.
- **AC-3** Lista validada contra a documentação atual da Meta (categoria Health/Wellness / assuntos sociais sensíveis).
- **AC-4** Fail-closed: na dúvida, bloqueia e pede revisão humana.

## Escopo
- IN: módulo de compliance + hook de validação no fluxo de upload.
- OUT: revisão jurídica externa; compliance de copy (é do time de criação).

## Dependências
`meta_ads.py` (ponto de upload). Nenhuma story bloqueante.

## Complexidade
Light-Medium.
