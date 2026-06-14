# Contrato da Pasta de Handoff do Caio (Campaign Inbox)

Como depositar campanhas prontas para o Caio subir na Meta **em PAUSED**. O Caio
faz polling desta pasta (story-058) e processa pacotes novos automaticamente.

## Estrutura

```
inbox/                          # raiz configurável (settings.yaml → inbox.folder)
  nw-ugc-ondas-001/             # 1 subpasta = 1 pacote de campanha
    manifest.yaml               # OBRIGATÓRIO (contrato abaixo)
    assets/
      ugc.mp4                   # mídia referenciada no manifest
  nw-carrossel-002/
    manifest.yaml
    assets/
      card1.jpg
      card2.jpg
  ... 
```

- Cada subpasta com `manifest.yaml` é um pacote. Sem `manifest.yaml` → ignorada.
- Processado com sucesso → o Caio cria o marcador `.caio_processed` (não reprocessa).
- Pacote inválido → **rejeitado** (notificação WhatsApp) e **não marcado** (corrija e ele tenta de novo no próximo poll).
- Polling: `settings.yaml → inbox.poll_minutes` (default 15 min). Modo `inbox.dry_run` (default **true** até as credenciais Meta entrarem).

## Contrato do `manifest.yaml`

### `campaign`
| Campo | Obrigatório | Valor |
|---|---|---|
| `name` | sim | nome da campanha |
| `product` | sim | `new_woman` / `alpha_pulse` |
| `objective` | não (default `OUTCOME_ENGAGEMENT`) | `OUTCOME_ENGAGEMENT` ou `OUTCOME_SALES` (`messages` é normalizado p/ ENGAGEMENT) |
| `status_on_upload` | não | deve ser `paused` (forçado) |
| `page_id` | sim | ID da fanpage (com o número WhatsApp vinculado) |
| `whatsapp_phone_number` | sim | número WhatsApp onde o vendedor (Lívia) atende |
| `version` | não (default `v1`) | `v1`, `v2`, ... (versionamento imutável) |

### `adset`
| Campo | Obrigatório | Valor |
|---|---|---|
| `name` | sim | nome do ad set |
| `daily_budget_brl` | sim (>0) | budget diário em R$ |
| `locations` | sim* | lista de países, ex. `["BR"]` |
| `age_min` / `age_max` | não | faixa etária |
| `gender` | não | `male` ou `female` |
| `optimization_goal` | não (default `CONVERSATIONS`) | mantenha `CONVERSATIONS` p/ CTWA |
| `billing_event` | não (default `IMPRESSIONS`) | |

\* alternativa: bloco `targeting` aninhado completo (`geo_locations`, etc.).

### `ads` (lista, mínimo 1)
Cada ad tem `format` (= `image`/`static`, `video` ou `carousel`):

**image / video (single-asset):**
| Campo | Obrigatório |
|---|---|
| `name`, `format`, `asset` (caminho relativo), `primary_text`, `headline` | sim |
| `cta` | não (default `SEND_MESSAGE` — ver nota CTWA) |

**carousel (multi-card, mínimo 2 cards):**
| Campo | Obrigatório |
|---|---|
| `name`, `format: carousel`, `primary_text`, `headline` | sim |
| `cards` (lista ≥2) — cada card: `asset` (obrigatório), `headline`, `primary_text?`, `link?` | sim |

> **Nota CTWA (ver `docs/research/ctwa-api-requirements.md`):** o objetivo é Click-to-WhatsApp —
> o clique abre conversa no WhatsApp do `whatsapp_phone_number` (onde a Lívia vende). No go-live com
> conta real, confirmar o CTA correto (`WHATSAPP_MESSAGE` vs `SEND_MESSAGE`) — é o único ponto
> empírico pendente; toda a estrutura de campanha/ad set já está validada.

## Exemplos prontos
Veja `docs/examples/manifests/`: `image.yaml`, `video.yaml`, `carousel.yaml`.

## Garantias do Caio
- Tudo nasce **PAUSED** (nada vai ao ar sem aprovação do pacote).
- Validação Pydantic antes de qualquer chamada à Meta (manifesto inválido = rejeitado sem tocar na API).
- Escala autônoma **bloqueada** sem venda paga atribuída + tetos definidos (story-060).
