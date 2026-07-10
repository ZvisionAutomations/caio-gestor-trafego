# Story 091 — Schema validation de tool calls [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-07)

> ⚠️ **Runtime atualizado (2026-07-05, hermes-v2-slicing §1.1):** o texto original (AC-1/AC-3 citando `agent/tool_validator.py` + `caio.py`/Agno) descreve o runtime Python LEGADO, que NÃO roda em produção. Produção é Hermes + `meta-ads-mcp` via npx (Node). A **intenção** dos ACs (validar schema de tool mutante, IDs `^\d+$`, fail-safe, extra=allow) foi preservada 1:1, mas implementada no **wrapper Node** `packages/meta-ads-mcp-guarded/` (proxy MCP), não em Python. @product-lead já re-validou o "onde" no slicing (mantém Ready).

### Dev Agent Record

**File List (novo pacote `packages/meta-ads-mcp-guarded/`):**
- `package.json` — pacote Node ESM, dep única `@modelcontextprotocol/sdk`.
- `src/validators.js` — **AC-1/AC-2/AC-5**: modelo de validação por tool mutante; `META_NUMERIC_ID = /^\d+$/`; `MUTATING_TOOLS` (nomes reais do meta-ads-mcp + aliases legados); valida IDs numéricos onde aparecerem; extra=allow (só valida campos conhecidos).
- `src/interceptors.js` — pipeline extensível (091 plugada; 088/089/094 entram depois); `runPipeline` **fail-open** (AC-4: guardrail com bug nunca derruba o agente).
- `src/index.js` — proxy MCP: spawna `meta-ads-mcp` real como filho, passthrough de tools/list e read-only; **AC-3**: roda a pipeline nas mutantes ANTES do dispatch pro filho; **AC-4**: erro do filho/validação vira MCP tool result estruturado (`isError`), nunca exceção.
- `test/validators.test.js`, `test/interceptors.test.js`, `test/proxy.test.js`, `test/mock-child.js` — suíte.
- `README.md`, `.gitignore`.

**Completion Notes:**
- Suíte **18/18 verde** (9 validators + 5 interceptors + 4 integração). O teste de integração sobe o proxy real contra um MCP filho mockado e prova end-to-end: passthrough de read-only, mutante válida repassada, e **mutante com ID alucinado (`act_hallucinated`) BLOQUEADA antes da Graph API** — sem precisar de credencial Meta.
- **GOTCHA de ambiente:** `npm install` falha com `EBADF` no Google Drive (`G:\Meu Drive`) — filesystem virtual. Testado instalando o SDK em disco NTFS local e rodando de lá. Em produção (VPS Linux) não ocorre. Documentado no README.
- Pendente pra go-live (fora do escopo de código desta story): apontar o MCP `meta-ads` do Hermes pra este proxy (config no README) — feito no deploy do rollout.
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §6.4
**Package:** caio-trafego

## Story Statement
**As** operador, **I want** validação de schema antes de qualquer tool call mutante do Caio, **so that** o GLM-4.7-flash nunca despache uma ação Meta com ID de API inventado (alucinação de adset/campaign inexistente).

## Contexto
`llm_router.py`/`caio.py` chamam tools sem validação entre a resposta do LLM e a execução. Research: modelos flash podem fabricar IDs numéricos plausíveis mas inválidos. MoA advisory (Fase 2) não resolve execução — a validação é o guardrail.

## Acceptance Criteria
- **AC-1** `agent/tool_validator.py` com 1 modelo Pydantic por tool mutante (`pause_ad_set`, `duplicate_ad_set`, `adjust_bid`, `create_ad`).
- **AC-2** `adset_id`/`campaign_id` devem ser **string numérica pura** (sem `act_`/`adset_`); regex `^\d+$`.
- **AC-3** Integrado no wrapper de tools do Agno em `caio.py`, antes do dispatch pro `MetaAdsTool`.
- **AC-4** Fail-safe: `ValidationError` nunca derruba o agente — retorna erro estruturado pro LLM reformular; loga schema recebido.
- **AC-5** `ConfigDict(extra="allow")` — valida só campos obrigatórios (evita falso negativo).

## Escopo
- IN: validator + integração nas tools mutantes.
- OUT: tools de leitura (não mutam); MoA (Fase 2).

## Dependências
`caio.py`, `meta_ads.py`.

## Complexidade
Medium.
