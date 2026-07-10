# Runbook — Checklist de destino WhatsApp por produto no manifest.yaml (story-095, AC-1)

> **Objetivo:** garantir que todo pacote de Campaign Inbox aponte o clique do anúncio (Click-to-WhatsApp) pro número certo. Sem isso, o erro é **silencioso** — o Meta não avisa que o clique caiu no número errado.
> **Schema-fonte:** `CampaignSpec` em `agent/campaign_inbox.py` (linhas 12-19) — `page_id` e `whatsapp_phone_number` já existem por campanha, não é preciso mudar código pra rotear por produto.

## Regra
Todo `manifest.yaml` de uma campanha (pasta do Campaign Inbox) **deve** declarar, dentro de `campaign:`:
```yaml
campaign:
  name: <nome da campanha>
  product: <AlphaPulse | New Woman>
  page_id: <Page ID do Meta Business correto pro produto>
  whatsapp_phone_number: <número WhatsApp correto pro produto>
  ...
```

## Tabela de destino por produto (preencher com os valores reais antes do 1º upload)

| Produto | Vendedor/canal | Page ID | WhatsApp phone number |
|---|---|---|---|
| AlphaPulse | Fernando (venda manual, sem bot) | `<preencher>` | `<preencher>` |
| New Woman | Lívia (bot automatizado) | `<preencher>` | `<preencher>` |

## Checklist antes de subir qualquer pacote (Campaign Inbox)
1. Confirmar o `product` declarado no manifest bate com a tabela acima.
2. Confirmar `page_id` do manifest == Page ID da linha correspondente da tabela.
3. Confirmar `whatsapp_phone_number` do manifest == número da linha correspondente da tabela.
4. Se o produto for novo (nem AlphaPulse nem New Woman), **parar** e adicionar uma linha nova na tabela acima antes de prosseguir — não assumir um destino.
5. Depois do upload (mesmo em modo `--dry-run`), conferir no preview do Meta Ads Manager que o botão do anúncio aponta pro número esperado.

## Por que isso importa (contexto)
- `InboxPackage.translate()` (`agent/campaign_inbox.py`) embute `page_id`/`whatsapp_phone_number` no `promoted_object` do adset e em cada ad — é isso que decide pra onde o clique vai. O código já suporta múltiplos produtos/números simultaneamente; o único risco é erro humano no preenchimento do manifest.
- Ver `docs/stories/story-095-caio-multi-produto-roteamento.md` para o desenho completo (inclui a decisão de que AlphaPulse roda em modo assistido, sem escala automática, já que o Fernando vende manualmente).

## Fora de escopo deste runbook
- Sinal de atribuição de venda / reinvestimento automático por produto — ver AC-3 (backlog) da story-095.
- Verificação de que a tool `upload_creative_from_inbox` (092b, ainda não implementada) preserva esses campos — ver AC-2 da story-095, fica pendente até a 092b existir.
