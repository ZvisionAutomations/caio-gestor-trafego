# Research — Requisitos da API Click-to-WhatsApp (CTWA) para o Caio

**Gate D9 (deep research) — story-059/A3/go-live.** Autor: @analyst (Scope) · 2026-06-14.
Fontes: doc oficial Meta Marketing API (CTWA) + guias técnicos consistentes (Kommo, Infobip, Woztell, AiSensy, Interakt). A doc oficial é JS-pesada (não rendeu via fetch), então confirmações empíricas finais ficam marcadas `[VERIFICAR NA CONTA REAL]`.

## 1. Confirmado (bate com o código atual)

| Camada | Campo | Valor | Onde no código |
|---|---|---|---|
| Campanha | `objective` | **`OUTCOME_ENGAGEMENT`** (ODAX; também aceita Leads/Sales/Awareness) | `CampaignSpec.objective` ✅ |
| Ad set | `destination_type` | **`WHATSAPP`** | `translate()` adset ✅ |
| Ad set | `optimization_goal` | **`CONVERSATIONS`** | `AdSetSpec.optimization_goal` ✅ |
| Ad set | `promoted_object` | `{ page_id }` (número WA vinculado à página) | `translate()` promoted_object ✅ |
| Creative | `object_story_spec.link_data` | `image_hash` + `call_to_action` (+ `link`) | `_story_data`/`_carousel_link_data` ✅ (parcial) |

→ A estrutura de **campanha + ad set** do Caio está **correta**.

## 2. 🔴 Achado: tipo do call_to_action

As fontes indicam que o CTA correto para CTWA é **`type: "WHATSAPP_MESSAGE"`**.
O código atual (`agent/tools/meta_ads.py:_story_data`) usa:
```python
cta = {"type": ad_payload.get("cta", "SEND_MESSAGE"), "value": {"app_destination": "WHATSAPP"}}
```
ou seja, default **`SEND_MESSAGE`** + `value.app_destination=WHATSAPP`. Há divergência:
- Provável correto: `call_to_action = {"type": "WHATSAPP_MESSAGE"}` (a Meta resolve o destino pelo `destination_type=WHATSAPP` do ad set + `promoted_object.page_id`).
- O `SEND_MESSAGE` + `app_destination` é padrão de Messenger/genérico e **pode** funcionar via SDK, mas **não é o documentado para CTWA**.

**Ação:** `[VERIFICAR NA CONTA REAL]` qual tipo a conta aceita. Recomendação: trocar o default para `WHATSAPP_MESSAGE` (ou tornar o tipo configurável no manifesto) — **não alterar agora** sem conta para validar (evita quebrar o que talvez já funcione). Registrar como tech-debt/go-live check.

## 3. `link_data` exige `link`
As fontes mostram `link_data` com `image_hash` + `link` + `call_to_action`. O `_story_data` single-image **não seta `link`**. Para CTWA o `link` costuma ser o link do WhatsApp/anúncio. `[VERIFICAR NA CONTA REAL]` se é obrigatório para `destination_type=WHATSAPP` (em muitos casos o destino vem do ad set e o `link` é opcional/placeholder). O carrossel (`_carousel_link_data`) já aceita `link` por card no contrato.

## 4. Carrossel (resolve o R-CAR no nível de design)
Carrossel = `object_story_spec.link_data.child_attachments` (lista). Cada card:
`{ image_hash, name (headline), description?, link?, call_to_action }`.
O `_carousel_link_data` do Caio (story-059) **já segue esse shape**. Resta confirmar na conta real:
- se cada card precisa do próprio `call_to_action`/`link` ou herda do `link_data` pai;
- o `type` do CTA (mesmo achado do item 2: `WHATSAPP_MESSAGE`).
→ R-CAR **reduzido a uma checagem empírica** no primeiro upload, não a uma incógnita de arquitetura.

## 5. Bônus: mensagem de boas-vindas
Há `object_story_spec.page_welcome_message` (greeting do WhatsApp ao clicar; suporta `ctwa_flows`/Flow). **Fora do escopo atual** do Caio (a Lívia conduz a conversa), mas mapeado para o futuro.

## 6. Resumo para A3 (contrato da pasta) e go-live
- Manifesto image/vídeo/carrossel: objetivo `OUTCOME_ENGAGEMENT`, optim `CONVERSATIONS`, `destination_type WHATSAPP`, `promoted_object.page_id` — tudo já no contrato.
- **No go-live (com conta real), checar:** (a) CTA `WHATSAPP_MESSAGE` vs `SEND_MESSAGE`; (b) obrigatoriedade do `link` em `link_data`; (c) CTA por card no carrossel. Tudo o resto está alinhado.

### Fontes
- [Meta — Click to WhatsApp (Marketing API)](https://developers.facebook.com/docs/marketing-api/ad-creative/messaging-ads/click-to-whatsapp/)
- [Kommo — CTWA](https://www.kommo.com/blog/click-to-whatsapp/) · [Infobip](https://www.infobip.com/blog/click-to-whatsapp-ads) · [Woztell](https://support.woztell.com/portal/en/kb/articles/guide-to-click-to-whatsapp-with-meta-ads) · [AiSensy](https://m.aisensy.com/blog/click-to-whatsapp-ads-guide/) · [Meta — child_attachment](https://developers.facebook.com/docs/marketing-api/reference/ad-creative-link-data-child-attachment/)
