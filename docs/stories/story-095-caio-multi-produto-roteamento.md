# Story 095 — Roteamento multi-produto (destino WhatsApp + sinal de atribuição por produto)

**Status:** Done

### Dev Agent Record (File List)
- `docs/runbooks/campaign-manifest-multi-produto-checklist.md` (novo) — checklist AC-1, tabela produto→Page ID/número (placeholders `<preencher>` pendentes dos valores reais do Fernando/Lívia).
- AC-2 **não implementado nesta passada**: a tool `upload_creative_from_inbox` (092b) ainda não existe no repo (confirmado via busca — só há fixtures de teste e exemplos de manifest). Fica registrado como item de checklist a ser verificado quando a 092b for construída; não é regressão nem bloqueio desta story.
- AC-4: nada a implementar — comportamento fail-safe já existente (sinal ausente → bloqueia escala) cobre o caso sem código novo.
**Epic:** Caio Gestor de Tráfego — expansão multi-produto (AlphaPulse + New Woman)
**Track:** Standard
**Complexidade:** Light (checklist operacional + verificação de não-regressão; zero código novo no escopo ativo — AC-3 é backlog)
**Valor de negócio:** Libera rodar AlphaPulse e New Woman em paralelo sem risco de misturar destino de clique ou estourar a trava de escala por engano.
**Owner sugerido:** @architect (design, feito) → @developer (Pixel) implementa a parte condicional (AC-3)
**Criada por:** @architect (Stratum) — 2026-07-07, in-thread (call Zvision + Kaue)
**Revisada por:** @sprint-lead (Sync) — 2026-07-07, formatação + checklist
**Validada por:** @product-lead (Axis) — 2026-07-07 — GO (10/10 checklist)

## Change Log
- 2026-07-07 — @architect (Stratum): rascunho criado in-thread (Draft).
- 2026-07-07 — @sprint-lead (Sync): revisão de formato, complexidade, riscos e Definition of Done adicionados.
- 2026-07-07 — @product-lead (Axis): validado G3, GO — Status Draft → Ready.
- 2026-07-07 — @developer (Pixel): AC-1 implementado (runbook criado). AC-4 já coberto pelo fail-safe existente, sem código novo. Status Ready → InProgress.
- 2026-07-07 — @product-lead (Axis): correção de escopo — AC-2 REMOVIDO (dependia de story 092b inexistente; a story ficaria presa em InProgress esperando algo que não é dela). Exigência preservada como nota obrigatória em `hermes-v2-slicing.md` §3 pra quando a 092b nascer. Com AC-1 e AC-4 completos e AC-3 backlog explícito, todos os ACs ativos estão satisfeitos. Status InProgress → **Done**. Pendência real fora desta story: preencher os valores reais (`<preencher>`) na tabela do runbook com Page ID/número do Fernando e da Lívia.

---

## Story Statement
**As** operador da Raiz Vital,
**I want** que o Caio saiba, por campanha/produto, pra qual número de WhatsApp mandar o clique do anúncio e (se decidido) de qual sinal de venda ler pra escalar,
**so that** dá pra rodar **AlphaPulse** (destino: número do Fernando) e **New Woman** (destino: número da Lívia) ao mesmo tempo sem misturar tráfego nem travar a escala por engano.

## Contexto (verificado no código, 2026-07-07)

### 1. Destino do clique (Click-to-WhatsApp) — JÁ FUNCIONA, sem mudança de código
- `agent/campaign_inbox.py` → `CampaignSpec` já tem `page_id: str` e `whatsapp_phone_number: str` **por campanha** (lidos do `manifest.yaml` de cada pacote).
- `InboxPackage.translate()` já embute os dois campos no `promoted_object` do adset e em cada ad (`_translate_ad`) — é assim que o Meta sabe pra onde mandar o clique.
- **Conclusão:** não existe gap de roteamento aqui. Cada pacote de campanha (pasta do Campaign Inbox) já declara seu próprio destino. Basta o operador preencher `page_id` + `whatsapp_phone_number` certos em cada manifest — AlphaPulse aponta pro Fernando, New Woman aponta pra Lívia.
- **Ressalva A:** confirmar que a 092b (`upload_creative_from_inbox`, tool MCP nova que substitui o `inbox_poller.py` legado — ver `hermes-v2-slicing.md` §3) preserva esses dois campos por campanha sem hardcode de um único número/page global. Checar ao implementar 092b.
- **Ressalva B (decisão externa, não é código):** confirmar no Meta Business Manager se a Page em uso suporta múltiplos números de WhatsApp vinculados ("multiple phone numbers per Page") ou se AlphaPulse precisa de uma Page própria. Perguntar ao Cauê/Fernando na call.

### 2. Sinal de negócio / atribuição de venda — GAP REAL, single-tenant hoje
- Legado (`agent/business_signal.py` + `agent/workflows/optimize.py`, **aposentado** pelo re-fatiamento Hermes v2 — ver `hermes-v2-slicing.md` item "✅ #1"): `tenant_id` é fixado **uma vez no boot** via `CAIO_SIGNAL_TENANT_ID` — nenhuma variação por adset/produto. Ilustra o problema mas não é onde a correção deve entrar (código morto em produção).
- v2 real (runtime Hermes): a atribuição via CAPI (story-087) e o reinvestimento (story-090, AC-3.2: `novo_teto = 300 + 0.20 × receita_atribuída_via_CAPI`) foram desenhados para **um** dataset/WABA — o da Lívia (New Woman). Não existe conceito de "produto" nem mapeamento produto→dataset/tenant em nenhum dos dois.
- **Consequência se não resolvido:** se as vendas do AlphaPulse (canal do Fernando) não alimentarem o mesmo dataset CAPI que a Lívia alimenta, o Caio nunca vai enxergar receita atribuída às campanhas AlphaPulse → o guardrail de reinvestimento (090) trava a escala automática desse produto **para sempre** (lado seguro, por design). Única saída seria aprovação manual via WhatsApp (fluxo já existe e continua funcionando).

## Decisão — RESOLVIDA (2026-07-07, call Zvision + Kaue)
**Fernando vende AlphaPulse manualmente, sem bot.** → Caminho **(b)**: AlphaPulse roda em **modo assistido** (Caio sugere, humano aprova/escala via WhatsApp), sem reinvestimento automático. **AC-3 vira backlog** (não implementar agora — só se um bot de vendas for adicionado no futuro). **AC-4 é o escopo ativo desta story.**

## Acceptance Criteria (Given/When/Then)

**AC-1 — Cada campanha declara seu próprio destino**
- **Given** um pacote de campanha (Campaign Inbox) para AlphaPulse ou New Woman,
- **When** o manifest.yaml é preenchido,
- **Then** `page_id` e `whatsapp_phone_number` correspondem ao número certo do produto (checklist operacional — sem código novo).

**AC-2 — REMOVIDO (2026-07-07, @product-lead)** — Movido pra fora desta story. "092b preserva o roteamento por campanha" é responsabilidade de implementação/QA da futura story 092b (ainda não rascunhada), não desta. Ver nota adicionada em `hermes-v2-slicing.md` §3 — quando a 092b for criada pelo @sprint-lead, ela deve nascer com esse AC. Motivo: um AC que só pode ser cumprido por outra story ainda inexistente prendia a story-095 em InProgress indefinidamente — escopo errado, corrigido.

**AC-3 — Sinal de atribuição por produto (BACKLOG — não implementar agora)**
- Fica documentado como referência futura, caso um bot de vendas seja adicionado ao canal do Fernando: mapeamento produto→tenant em `config.yaml`, inferido do `campaign.product` do manifest (reusa padrão de `report.py::_infer_product`), fail-safe idêntico ao já usado (sinal ausente → bloqueia).
- **Não faz parte do escopo desta story.** Não criar código para isso agora.

**AC-4 — Modo assistido (escopo ativo, decisão confirmada = manual)**
- **Given** AlphaPulse sem dataset CAPI (Fernando vende manualmente),
- **When** o Caio avalia escalar uma campanha AlphaPulse,
- **Then** nunca escala sozinho (sinal sempre vazio pra esse produto, comportamento fail-safe já existente — nenhum código novo necessário) — sugestão só via aprovação manual no WhatsApp; isso é esperado e documentado, não um bug.
- **Verificação:** confirmar que `CAIO_SIGNAL_TENANT_ID`/dataset do New Woman continuam intocados (sem regressão na Lívia) quando AlphaPulse entrar em produção.

## Escopo
### IN
- Checklist operacional de preenchimento do manifest por produto (AC-1).
- Verificação de não-regressão do sinal da Lívia/New Woman quando AlphaPulse subir (AC-4).
### OUT
- Mapeamento produto→tenant / dataset CAPI para AlphaPulse (AC-3) — backlog, só se um bot de vendas for adicionado no futuro.
- Preservar roteamento por campanha na 092b (era AC-2) — pertence à futura story 092b, não a esta.
- Criar um novo bot/fluxo de captura de vendas pro Fernando.
- Mudar a lógica de `evaluate_scale_guardrails` em si.
- Página/BM setup (Ressalva B) — decisão externa do Cauê/Fernando, não implementação.

## Dependências
- Reusa `campaign_inbox.py` (sem mudança). Depende de 087 (CAPI) + 090 (rules engine) apenas se o backlog AC-3 for retomado no futuro. Não depende mais da 092b (AC-2 removido, virou responsabilidade daquela story).

## Riscos
- **Confusão operacional:** operador preencher `page_id`/`whatsapp_phone_number` errado no manifest e o clique do AlphaPulse cair no número da Lívia (ou vice-versa) — mitigado pelo checklist AC-1 (revisão antes do upload).
- **Regressão silenciosa na 092b:** quando ela for implementada, hardcodar destino por engano — mitigado pela nota em `hermes-v2-slicing.md` §3 garantindo que o AC nasça junto com aquela story.
- **Expectativa de escala automática:** sem AC-3, alguém pode esperar que o AlphaPulse escale sozinho como o New Woman — mitigado pelo AC-4 (documentado como comportamento esperado, não bug).

## Definition of Done
- Checklist AC-1 aplicado nos dois manifests em uso (AlphaPulse, New Woman) e conferido por um humano antes do primeiro upload de cada.
- AC-4 confirmado em ambiente real: campanha AlphaPulse rodando sem escalar sozinha; New Woman sem regressão de sinal.
- Nota de roteamento (ex-AC-2) registrada em `hermes-v2-slicing.md` §3 pra não se perder quando a 092b for rascunhada.

## QA
- Tipo: Config/Roteamento. Foco: nenhuma regressão no fluxo single-produto atual (New Woman/Lívia); fail-safe idêntico ao padrão já usado (sinal ausente → bloqueia, nunca escala por engano).
