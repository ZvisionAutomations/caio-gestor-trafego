# Mensagem pro Cauê — liberar credenciais Meta (CAPI) do Caio

> **Objetivo:** desbloquear as stories 087/090 (atribuição de venda + reinvestimento). Cauê/Fernando têm o acesso admin ao Business Manager.
> Use a **Parte 1** como mensagem direta (WhatsApp/e-mail). A **Parte 2** é o passo-a-passo técnico pra anexar/encaminhar a quem for clicar no Business Manager.

---

## Parte 1 — Mensagem pronta pra enviar

> **Assunto: Liberar 2 credenciais da Meta pro Caio medir as vendas do WhatsApp**
>
> Fala, Cauê! Beleza?
>
> Tô colocando o Caio (nosso gestor de tráfego automático da Raiz Vital) pra **enxergar quais anúncios geram venda de verdade no WhatsApp** — hoje ele otimiza meio no escuro porque a venda acontece na conversa e o Meta não sabe que veio do anúncio. Com isso ligado, ele passa a cortar o que não vende e escalar o que vende (a gente inclusive quer reinvestir 20% do faturamento nos anúncios que estão performando).
>
> Pra isso eu preciso de **2 coisas** do Business Manager (você/Fernando são admin):
>
> **1. Dataset ID** da conta de anúncios `act_1745516809747438` (Events Manager → é um número).
> **2. Um token de System User** com a permissão `whatsapp_business_manage_events` (+ `business_management`), com o dataset, o WhatsApp Business e a conta de anúncios atribuídos a ele.
>
> E **1 confirmação importante:** o número do WhatsApp que recebe os cliques do anúncio (Click-to-WhatsApp) está registrado como **WhatsApp Business oficial dentro do Meta Business** (WABA / Cloud API)? Ou está só num número comum/API não-oficial? Isso muda o caminho técnico — se não souber de cabeça, me diz que a gente verifica junto.
>
> ⚠️ O token é **secreto** (dá acesso de escrever eventos) — me manda por um canal seguro (cofre de senha, ou apaga a mensagem depois), nunca precisa colar em grupo.
>
> Se preferir, te mando o passo-a-passo com print de onde clicar, ou faço junto contigo numa call de 15 min. Valeu! 🙏

---

## Parte 2 — Passo-a-passo técnico (pra quem executar no Business Manager)

**Entregáveis:** `ZWAF_CAPI_DATASET_ID` (número) + `ZWAF_CAPI_TOKEN` (token) + resposta do WABA.

### A. Confirmação do WhatsApp (fazer primeiro)
- O número de Click-to-WhatsApp está num **WABA oficial** (WhatsApp Business Platform / Cloud API) ligado ao Business?
  - **Sim** → seguir normal (dataset Business Messaging).
  - **Não / é número não-oficial (Baileys/Evolution)** → me avisar: usamos o **fallback** (CAPI no dataset da conta de anúncios com o identificador do clique em `custom_data`). Funciona, atribuição só um pouco mais fraca. Não trava o projeto.

### B. Dataset ID
1. business.facebook.com → **Gerenciador de Eventos (Events Manager)**.
2. Achar o **dataset** vinculado à conta `act_1745516809747438` (ou ao WABA).
3. Copiar o **Dataset ID** (numérico).

### C. Token de System User
1. **Configurações do Negócio → Usuários → Usuários do Sistema** → criar/usar um System User (Admin ou Employee).
2. **Gerar novo token** → escolher o app do Business → marcar permissões: **`whatsapp_business_manage_events`** + **`business_management`** (e `ads_management` se for o mesmo user que o Caio já usa pro MCP).
3. Copiar o token (permanente) → **guardar em cofre**.
4. **Atribuir ativos** ao System User: o dataset (B) + o WABA + a conta de anúncios `act_1745516809747438`, com permissão de gerenciar eventos.

### D. Entrega
- Mandar por canal seguro: `Dataset ID` + `Token`. Vão pro `.env` do zwaf na VPS na hora de implementar (nunca no repo/chat).

### E. Validação (a gente faz depois, do nosso lado)
- Events Manager → dataset → **Testar Eventos** → disparamos um `Purchase` de teste e confirmamos EMQ ≥ 7.0.

---

**Status:** aguardando Cauê/Fernando. É o único bloqueio externo que trava o deploy das 087/090 (o resto — 088/089/091/092a/094 — não depende disso e pode ser implementado antes).
