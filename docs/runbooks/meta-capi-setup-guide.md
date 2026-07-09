# Runbook — Setup Meta CAPI Business Messaging (manual)

> **Bloqueio A** das stories 087/090. **Acesso admin = Kauê/Fernando** (pendência externa).
> 📩 **Mensagem pronta pra pedir ao Cauê:** `mensagem-caue-meta-credentials.md` (Parte 1 = texto direto; Parte 2 = passo-a-passo técnico).
> Método: manual (dashboard). Objetivo: produzir 2 secrets → `ZWAF_CAPI_DATASET_ID` e `ZWAF_CAPI_TOKEN`.
> Não commitar secrets — vão no `.env` do zwaf na VPS.

## ⚠️ Passo 0 — Verificação bloqueante (fazer ANTES)

O CAPI **Business Messaging** (`action_source=business_messaging`, `messaging_channel=whatsapp`) se apoia num **WhatsApp Business Account (WABA) oficial** ligado ao Business. A Lívia hoje usa **Evolution API (não-oficial/Baileys)**.
- ✅ Captura do `ctwa_clid` já funciona (story-039 provou — vem no `contextInfo`/referral).
- ❓ **Confirmar:** o número de CTWA está num WABA oficial no Meta Business? Se **sim** → segue o guia. Se **não** → o envio server-side de `Purchase` via BM pode ser rejeitado; alternativas: (a) migrar o número pra WhatsApp Cloud API oficial, ou (b) usar CAPI com `action_source=other` + dataset de ads (atribuição por `ctwa_clid` em custom_data) — validar com @architect antes.

> **Research 2026-07-04:** On-Premises WhatsApp API foi encerrado (out/2025); **Cloud API = caminho oficial**. A **captura** do `ctwa_clid` via Evolution/Baileys funciona (story-039 provou — vem no `contextInfo`). O **envio** do Purchase via CAPI BM se apoia num dataset ligado ao WhatsApp Business Platform → **risco:** número em Baileys não-oficial pode não ter dataset BM válido. **Fallback:** CAPI no dataset da **conta de anúncios** com `ctwa_clid` em `custom_data` (atribuição um pouco mais fraca, mas funciona). Confirmar no account real.

## Passo 1 — Dataset (Events Manager)
1. business.facebook.com → **Events Manager** → **Connect Data Sources**.
2. Localizar/criar o **dataset** vinculado ao WABA / conta de anúncios `act_1745516809747438`.
3. Copiar o **Dataset ID** (numérico) → vira `ZWAF_CAPI_DATASET_ID`.

## Passo 2 — System User + token
1. **Business Settings → Users → System Users** → criar (ou usar existente) System User (role Admin ou Employee).
2. **Generate New Token** → app do Business → permissões: **`whatsapp_business_manage_events`** (+ `business_management`; `ads_management` se for o mesmo user do MCP).
3. Copiar o token (permanente) → vira `ZWAF_CAPI_TOKEN`. **Guardar em cofre**, nunca em chat/repo.
4. **Assign assets** ao System User: o dataset (passo 1) + o WABA + a conta de anúncios, com permissão de gerenciar eventos.

## Passo 3 — Entregar os secrets (na VPS, na hora de implementar)
No `.env` do zwaf (`/opt/zwaf/packages/zwaf/.env` — confirmar caminho):
```
ZWAF_CAPI_DATASET_ID=<dataset_id>
ZWAF_CAPI_TOKEN=<system_user_token>
```
Escapar `$` como `$$` se o valor tiver `$` (gotcha do docker-compose, ver hostinger-rescue).

## Passo 4 — Teste (antes de ligar em produção)
1. Events Manager → dataset → **Test Events** → copiar o `test_event_code`.
2. Disparar um `Purchase` sintético via `/{dataset_id}/events` com `test_event_code`, `action_source=business_messaging`, `ph`=hash de um número de teste.
3. Confirmar que aparece em Test Events com **EMQ ≥ 7.0**.

## Checklist de saída
- [ ] Passo 0 (WABA) confirmado/decidido
- [ ] `ZWAF_CAPI_DATASET_ID` obtido
- [ ] `ZWAF_CAPI_TOKEN` obtido e guardado em cofre
- [ ] Dataset+WABA+ad account atribuídos ao System User
- [ ] Test Event validado (EMQ ≥ 7.0)
