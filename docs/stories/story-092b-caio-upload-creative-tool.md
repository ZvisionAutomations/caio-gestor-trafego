# Story 092b — Tool MCP `upload_creative_from_inbox` (upload idempotente de criativos) [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-09). Pendente: aplicar migration 014 na VPS + `npm install` no wrapper + verificar assinaturas reais das tools do meta-ads-mcp.
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/hermes-v2-slicing.md` §3 (split da 092) + `story-095` (AC de roteamento multi-produto)
**Package:** meta-ads-mcp-guarded (artefato A) + migration no zwaf
**Criada por:** @sprint-lead (Sync) — 2026-07-07
**Complexidade:** Medium-Heavy

> ⚠️ **Runtime:** tool NOVA dentro do wrapper Node `packages/meta-ads-mcp-guarded/` (não Python). Substitui o papel do `inbox_poller.py` legado, que o Hermes NÃO herda. Padrão: os módulos já existentes em `src/` (091/088/089/090/094).

## Story Statement
**As** operador da Raiz Vital,
**I want** uma tool MCP determinística que pegue os pacotes de campanha que o rclone (092a) deposita em `/opt/caio/inbox/` e suba pro Meta em PAUSED, de forma idempotente,
**so that** eu solto criativos numa pasta do Drive e o Caio sobe sozinho — sem o LLM parsear manifest (risco de alucinação/double-spend) e sem subir o mesmo criativo duas vezes.

## Contexto (verificado)
- **092a** (rclone) entrega os arquivos + `manifest.yaml` em `/opt/caio/inbox/<campanha>/` — mas nada consome (o `inbox_poller.py` era do runtime Python morto).
- Schema do manifest já existe e é reusado: `packages/caio-trafego/agent/campaign_inbox.py::CampaignManifest` (`campaign`+`adset`+`ads`; cada `campaign` tem `page_id` e `whatsapp_phone_number`). A tool NÃO redefine o schema — valida contra ele.
- O wrapper (artefato A) já intercepta as tools mutantes com guardrails 088/091/094 — a cadeia de upload passa por eles automaticamente.
- **Furo C (slicing):** upload é multi-passo (`upload_ad_image` → `create_ad_creative` → `create_ad`). Um marker simples (`.caio_processed`) não basta: se falhar no meio, re-run duplicaria o creative. Precisa de **ledger transacional**.

## Acceptance Criteria (Given/When/Then)

**AC-1 — Varredura de pacotes não processados**
- **Given** `/opt/caio/inbox/` com subpastas de campanha,
- **When** a tool `upload_creative_from_inbox` roda (input opcional `campaign_folder`; default varre tudo),
- **Then** processa só subpastas **sem** o marker `.caio_processed`; ignora as já processadas.

**AC-2 — Validação de manifest (fail-safe, não sobe lixo)**
- **Given** um pacote,
- **When** a tool lê `manifest.yaml`,
- **Then** valida contra o schema `CampaignManifest`; se inválido → **pula o pacote, reporta o motivo, não sobe nada** (não derruba os outros pacotes).

**AC-3 — Cadeia de upload em PAUSED via guardrails**
- **Given** um manifest válido,
- **When** a tool sobe,
- **Then** chama `upload_ad_image` (ou vídeo) → `create_ad_creative` → `create_ad` no adset/campanha do manifest, tudo em **PAUSED**; cada chamada passa pelos interceptors do wrapper (091 schema, 088 guardian, 094 compliance).

**AC-4 — Roteamento multi-produto (herdado da story-095 — OBRIGATÓRIO)**
- **Given** pacotes de produtos diferentes (ex.: AlphaPulse, New Woman),
- **When** a tool monta o payload de cada ad,
- **Then** usa `page_id` e `whatsapp_phone_number` do manifest **daquele pacote individualmente** — **nunca** um valor global hardcoded. É o que garante AlphaPulse→número do Fernando e New Woman→número da Lívia sem misturar destino de clique.

**AC-5 — Idempotência por ledger (furo C)**
- **Given** um upload que falhou no meio (ex.: creative criado, ad não),
- **When** a tool roda de novo,
- **Then** consulta o ledger `caio_upload_ledger` (keyed por **hash do manifest + assets**), **retoma do passo pendente** reusando os IDs Meta já criados (image_hash/creative_id) — nunca reinicia do zero nem duplica.

**AC-6 — Commit da "transação"**
- **Given** a cadeia completou até o `create_ad` final com sucesso,
- **When** o último passo confirma,
- **Then** o marker `.caio_processed` é escrito **só então** (é o commit); antes disso, o estado vive no ledger.

**AC-7 — Resumo estruturado**
- **Given** uma execução,
- **When** termina,
- **Then** retorna resumo (`subiu X, pulou Y, erro Z, retomou W`) que o Hermes relata no Telegram.

## Escopo
### IN
- Tool `upload_creative_from_inbox` no wrapper (`packages/meta-ads-mcp-guarded/src/`), registrada como tool nova do MCP (além do passthrough).
- Leitura/validação do manifest (reusa o schema `CampaignManifest`).
- Ledger `caio_upload_ledger` (persistência da idempotência multi-passo).
- Escrita do marker `.caio_processed` no commit.
### OUT
- rclone/sync (é a 092a).
- Geração/scoring de criativo (Fase 2).
- Mudança no schema do manifest (só consome o existente).

## Dependências
- **092a** (rclone traz os arquivos pra VPS) — ✅ deployado e rodando em produção (2026-07-09).
- **091** (wrapper A existir) — ✅ já implementado (Ready for Review, 2026-07-07).
- **DB (@data-engineer):** nova tabela `caio_upload_ledger` (`manifest_hash`, `step`, `meta_id`, `status`, timestamps) → migration no `packages/zwaf/infra/migrations/` (mesmo padrão da `012_caio_adset_state.sql`). Próxima migration disponível: `014` (a `013` foi consumida pela story-087 `capi_dispatch_log`). Marcar envolvimento do @data-engineer.

## QA
- Tipo: Feature/Idempotência. Foco: multi-passo com falha no meio NÃO duplica creative (ledger retoma); manifest inválido não derruba os outros; roteamento por-campanha (AC-4) sem hardcode. Testável com MCP filho mockado (padrão `test/proxy.test.js` do wrapper) + ledger in-memory.

## Riscos
- **Double-spend** se o ledger falhar → mitigado por escrever o ID Meta a cada sub-passo antes de avançar; `.caio_processed` só no fim.
- **Assinatura real das tools** (`upload_ad_image`/`create_ad_creative`/`create_ad`) do `meta-ads-mcp` só confirma na VPS — marcar verificação de integração no deploy.

## Dev Agent Record

**Agent:** Pixel (@developer) · **Data:** 2026-07-09 · **Runtime:** Node ESM (`meta-ads-mcp-guarded`)

### File List
- `packages/meta-ads-mcp-guarded/src/upload_inbox.js` (novo) — `validateManifest` (espelho enxuto do `CampaignManifest`), `fingerprintAssets`+`manifestHash`, `scanInbox`, `buildSteps` (tradução → cadeia ordenada), `extractMetaId`, `uploadPackage` (resume via ledger + commit do marker), `runUploadFromInbox` (orquestração + resumo).
- `packages/meta-ads-mcp-guarded/src/upload_ledger.js` (novo) — `InMemoryUploadLedger` + `PgUploadLedger` + fábrica (mesmo padrão do `state_store.js`).
- `packages/meta-ads-mcp-guarded/src/index.js` (alterado) — registra `upload_creative_from_inbox` no `tools/list`; intercepta no `tools/call`; extrai `callGuardedTool` (a cadeia reusa a pipeline 091/088/094 — AC-3).
- `packages/zwaf/infra/migrations/014_caio_upload_ledger.sql` (+ rollback) (novo) — tabela `caio_upload_ledger` (PK `manifest_hash, step_key`).
- `packages/meta-ads-mcp-guarded/test/upload_inbox.test.js` (novo) — 12 testes.

### Completion Notes
- **AC-1** ✅ `scanInbox` varre `/opt/caio/inbox` (env `CAIO_INBOX_DIR`), input opcional `campaign_folder`; ignora pastas com `.caio_processed`.
- **AC-2** ✅ `validateManifest` contra o schema; inválido → `skipped` com motivo, **não sobe nada e não derruba os outros** pacotes.
- **AC-3** ✅ Cadeia `create_campaign → create_adset → (upload_ad_image|video → create_ad_creative → create_ad)` em PAUSED, via `callGuardedTool` (passa pelos interceptors do wrapper).
- **AC-4** ✅ Roteamento por-pacote: `page_id`/`whatsapp_phone_number` vêm do manifest daquele pacote (nunca global). Testado com 2 produtos (PAGE_ALPHA vs PAGE_NW).
- **AC-5** ✅ Ledger `caio_upload_ledger` keyed por hash(manifest+assets)+step; falha no meio → re-run **retoma** reusando IDs, sem duplicar. Testado (falha na 3ª call → 2 passos retomados).
- **AC-6** ✅ Marker `.caio_processed` só escrito após o `create_ad` final (commit).
- **AC-7** ✅ Resumo estruturado (`subiu/retomou/pulou/erro/total`) no retorno da tool.

### Testes
- **Suíte nova:** 12/12 passando.
- **⚠️ Ambiente:** os testes do wrapper **não rodam no mount do GDrive** — `node_modules/yaml/package.json` da raiz está com **0 bytes** (corrompido pelo sync) e `npm install` falha no GDrive (EPERM/EBADF, limitação do Drive File Stream). Isso quebra até os testes pré-existentes (`rules.test.js`). Rodei os 12 testes num harness local em C: (yaml real) → **12/12 ✅**. `node --check` OK nos 3 arquivos. **Na VPS (Linux) isso não ocorre** — basta `npm install` no wrapper.

### Pendente para produção
1. @devops: `npm install` no `packages/meta-ads-mcp-guarded/` na VPS (nunca foi instalado).
2. @devops: aplicar migration `014_caio_upload_ledger.sql` na VPS + secret `CAIO_DB_WRITE_URL` (role de escrita).
3. **Verificar assinaturas reais** das tools `create_campaign`/`create_adset`/`upload_ad_image`/`create_ad_creative`/`create_ad` do `meta-ads-mcp` na VPS — os arg-shapes em `buildSteps` seguem `campaign_inbox.py::translate()` mas só confirmam ao vivo; ajustar `buildArgs`/`extractMetaId` se divergir. [NEEDS VERIFICATION]

### Change Log
- 2026-07-09 — Implementação da tool `upload_creative_from_inbox` (scan+validate+ledger+resume+commit), migration 014, 12 testes. Status Ready → Ready for Review.
