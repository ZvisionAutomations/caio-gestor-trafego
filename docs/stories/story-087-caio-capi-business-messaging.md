# Story 087 — CAPI Business Messaging (Purchase + proxy) [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-09; credenciais Meta confirmadas). Pendente: aplicar migration 013 + secrets na VPS + smoke sintético (EMQ ≥ 7).
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Heavy (cross-system zwaf↔Caio)
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §6.3
**Package:** zwaf (dono da atribuição e da confirmação de venda)

## Story Statement
**As** operador da Raiz Vital, **I want** que toda venda confirmada no WhatsApp dispare um evento `Purchase` na Meta via CAPI Business Messaging, **so that** o algoritmo otimize por compra real (não por clique/conversa) e o Caio possa escalar por venda atribuída.

## Contexto
`lead_attribution.py` já captura `ctwa_clid` do webhook referral. `funnel_events.py` tem `PAYMENT_CONFIRMED` mas nenhum dispatcher CAPI wired. CAPI mora 100% no zwaf (privacidade — Caio só vê a view agregada `caio_attribution_signal`).

## Acceptance Criteria
- **AC-1** `zwaf/capi/dispatcher.py` envia `Purchase` com `action_source: business_messaging`, `messaging_channel: whatsapp`, `event_time`, `currency: BRL`, `value`, `user_data.ph` (hash) e `custom_data.ctwa_clid`.
- **AC-2** Lookup do `ctwa_clid` por telefone em `lead_attribution` antes do dispatch.
- **AC-3** Hash **SHA-256 sobre telefone normalizado E.164 com 9º dígito BR** (`+55DD9XXXXXXXX`); função de normalização trata 8→9 dígitos e DDI ausente.
- **AC-4** `InitiateCheckout` disparado quando o link Pix é gerado (proxy de volume baixo), mesmos campos de roteamento.
- **AC-5** Wire no `payment_gate.py` no caminho de confirmação; dispatch isolado (`asyncio.create_task`) — falha de CAPI **nunca** bloqueia a venda. Retry (tenacity 3×). Log em `capi_dispatch_log` (sem PII).
- **AC-6** Secrets `ZWAF_CAPI_DATASET_ID` / `ZWAF_CAPI_TOKEN` (system user token) em env, nunca em código. Testar com evento sintético antes de produção.

## Escopo
- IN: dispatcher CAPI, wire no payment_gate, InitiateCheckout proxy, normalização/hash LGPD, log.
- OUT: mudança no `lead_attribution.py` (já ok); lógica de otimização do Caio (story-090).

## Dependências
`lead_attribution.py` (Done, story-039), sinal de venda (story-060). Dataset/token Meta = decisão de setup (Kauê/Fernando).

## Complexidade
Heavy — cruza 2 sistemas, LGPD, integração Graph API. Sugerir faseamento F1–F6 na validação.

## Dev Agent Record

**Agent:** Pixel (@developer) · **Data:** 2026-07-09 · **Runtime:** zwaf (Python)

### File List
- `packages/zwaf/src/zwaf/capi/__init__.py` (novo) — pacote CAPI + re-exports.
- `packages/zwaf/src/zwaf/capi/dispatcher.py` (novo) — normalização E.164 BR + hash SHA-256, `load_settings`, lookup `ctwa_clid`, `build_event`, `dispatch_purchase`/`dispatch_initiate_checkout` (tenacity 3×, best-effort), `capi_dispatch_log` sem PII, schedulers fire-and-forget.
- `packages/zwaf/src/zwaf/api/routes/payment_webhook.py` (alterado) — wire do `Purchase` no caminho PAID real (`_dispatch_capi_purchase`, event_id = payment_id).
- `packages/zwaf/src/zwaf/conversion/payment_gate.py` (alterado) — wire do `InitiateCheckout` quando link Pix é gerado (`_maybe_dispatch_initiate_checkout`).
- `packages/zwaf/infra/migrations/013_capi_dispatch_log.sql` (+ rollback) (novo) — tabela de log PII-free.
- `packages/zwaf/tests/unit/test_capi_dispatcher.py` (novo) — 24 testes.

### Completion Notes
- **AC-1** ✅ Purchase com `action_source=business_messaging`, `messaging_channel=whatsapp`, `event_time`, `currency=BRL`, `value` (centavos÷100), `user_data.ph` (hash), `ctwa_clid`.
- **AC-2** ✅ `lookup_ctwa_clid(tenant, phone)` na `lead_attribution` (mais recente) antes do dispatch.
- **AC-3** ✅ Hash SHA-256 sobre E.164 BR com 9º dígito; `to_e164_br` trata 8→9, DDI ausente, zeros de acesso e preserva DDD 55. Hash é digits-only (spec Meta remove o `+`).
- **AC-4** ✅ InitiateCheckout no `payment_gate` quando link Pix gerado (proxy). **Nota:** só dispara p/ rail Pix e resultado de sucesso.
- **AC-5** ✅ Dispatch isolado via `asyncio.create_task` (schedulers) — falha CAPI nunca bloqueia a venda; retry tenacity 3× (só transporte/5xx); log em `capi_dispatch_log` sem PII.
- **AC-6** ✅ Secrets `ZWAF_CAPI_DATASET_ID`/`ZWAF_CAPI_TOKEN` só via env; desabilita graciosamente sem config (`skipped_no_config`).
- **Desvio honesto do texto do escopo:** o `Purchase` foi ligado no `payment_webhook.py` (ponto real de confirmação PAID do Asaas), não no `payment_gate.py` — este último gera o link, não confirma a venda. O `payment_gate.py` recebeu apenas o `InitiateCheckout` (AC-4). Decisão fiel ao AC-1 ("toda venda confirmada").
- **WABA fallback (caveat runbook):** `ZWAF_CAPI_ACTION_SOURCE=other` remove `messaging_channel` e espelha `ctwa_clid` em `custom_data` (dataset da conta de anúncios). Código tolerante — não hardcoda WABA oficial.
- **Config extra (env opcional):** `ZWAF_CAPI_API_VERSION` (default `v21.0`), `ZWAF_CAPI_ACTION_SOURCE` (default `business_messaging`), `ZWAF_CAPI_TEST_EVENT_CODE` (para Test Events).

### Testes
- **Suíte nova:** 24/24 passando (`test_capi_dispatcher.py`).
- **Regressão zwaf:** 520 passando; **2 falhas pré-existentes** (`test_payment_tool.py::test_card_message_embeds_value_with_markup` e `..._card_returns_link_message_no_pixqrcode`) — drift de copy do cartão da Lívia ("à vista" sem "parcelamento"), **confirmado reproduzível com meu código em stash** (baseline). Sem relação com a 087.

### Pendente para produção (smoke)
1. @devops: aplicar `013_capi_dispatch_log.sql` na VPS (e a 012 pendente, se ainda não aplicada).
2. Setar `ZWAF_CAPI_DATASET_ID` + `ZWAF_CAPI_TOKEN` no `.env` do zwaf (escapar `$`→`$$` no compose).
3. Confirmar Passo 0 WABA (runbook) — se número não for WABA oficial, setar `ZWAF_CAPI_ACTION_SOURCE=other`.
4. Test Event sintético (`ZWAF_CAPI_TEST_EVENT_CODE`) → validar EMQ ≥ 7.0 antes de ligar em produção.

### Change Log
- 2026-07-09 — Implementação inicial da CAPI (Purchase + InitiateCheckout), migration 013, testes. Status Ready → Ready for Review.
