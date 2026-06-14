# Story 059 — Suporte a carrossel multi-card no contrato de handoff

**Status:** Ready
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Track:** Standard
**Owner sugerido:** @developer (Pixel)
**Criada por:** @sprint-lead (Sync) — 2026-06-14
**Validada por:** @product-lead (Axis) — 2026-06-14 — GO (gate R-CAR mantido bloqueante de AC-4/AC-5; retrocompat single-asset coberta; dry-run construível agora)

---

## Story Statement

**As** operador da Raiz Vital,
**I want** que o contrato da pasta de handoff e o tradutor do Caio representem corretamente anúncios em **carrossel** (múltiplos cards),
**so that** os criativos de carrossel gerados (Higgsfield) possam virar campanhas Meta válidas — hoje só estático e UGC (vídeo) funcionam de fato.

---

## Contexto (verificado no código)
- `agent/campaign_inbox.py` → `AdSpec.format` **aceita** `image`/`static`, `video`, `carousel` (validador normaliza). **MAS** `AdSpec` tem um único campo `asset` e `InboxPackage.translate()` emite **um único `asset_path` por ad**.
- Para **carrossel**, a Graph API exige `object_story_spec` com **múltiplos cards** (`child_attachments`: N imagens + headline/descrição/link por card). O contrato single-asset **não representa** isso → carrossel é aceito na validação mas **não traduz** para um objeto Meta válido.
- `agent/tools/meta_ads.py` (`_create_ctwa_creative`) monta o creative — precisará de um caminho para carrossel multi-card.
- Decisão de escopo (memória `caio-gestor-trafego-escopo`): Higgsfield gera **formatos mistos (estático, carrossel, UGC)**; o contrato precisa suportar os 3.

## 🔬 Gate de research leve (D9 — condicional)
- **R-CAR — formato exato do carrossel CTWA na Graph API atual:** confirmar a estrutura de `object_story_spec` para carrossel Click-to-WhatsApp (uso de `child_attachments`, campos por card, limites mín/máx de cards, compatibilidade com `destination_type=WHATSAPP`/`promoted_object` CTWA). `[NEEDS VERIFICATION]` contra a Graph API vigente antes de implementar a camada de criação. (Pode ser resolvido pelo @analyst ou pelo @architect.)

---

## Acceptance Criteria (Given/When/Then)

**AC-1 — Schema multi-card no manifest**
- **Given** um `manifest.yaml` com um ad `format: carousel`,
- **When** o pacote é carregado,
- **Then** o schema aceita uma lista `cards` (cada card: `asset` obrigatório, `headline`, `primary_text?`, `link?`), com **mínimo de 2 cards** (validação falha com mensagem clara se <2).

**AC-2 — Retrocompatibilidade single-asset**
- **Given** um ad `format: image`/`static` ou `video`,
- **When** carregado,
- **Then** continua usando o campo `asset` único como hoje (sem `cards`), sem regressão nos manifests existentes.

**AC-3 — Validação de assets do carrossel**
- **Given** um ad carrossel,
- **When** `validate_assets` roda,
- **Then** verifica a existência de **cada** asset de **cada** card (não só um), com issue por card faltante.

**AC-4 — Tradução para objeto Meta multi-card**
- **Given** um ad carrossel válido,
- **When** `translate()` roda,
- **Then** emite uma estrutura multi-card (lista de cards com asset_path resolvido + headline/text/link) compatível com o `object_story_spec`/`child_attachments` confirmado em R-CAR; ads single-asset mantêm o shape atual.

**AC-5 — Camada de criação monta o carrossel**
- **Given** a estrutura traduzida de carrossel,
- **When** `meta_ads._create_ctwa_creative` (ou equivalente) processa,
- **Then** monta o `object_story_spec` de carrossel CTWA (modo real exige credenciais Meta; testável em dry-run/mocks). Single-asset (image/video) inalterado.

**AC-6 — Harness/testes verdes**
- **Given** a suíte,
- **When** executada,
- **Then** novo harness cobre: manifest de carrossel válido traduz para multi-card; carrossel com <2 cards é rejeitado; card com asset faltante é rejeitado; image/video single-asset sem regressão. ruff + mypy limpos.

---

## Escopo
### IN
- Extensão do schema Pydantic (`AdSpec` + novo `CardSpec`) em `agent/campaign_inbox.py`.
- `validate_assets` cobrindo cards.
- `InboxPackage.translate()` emitindo multi-card p/ carrossel.
- Caminho de carrossel em `agent/tools/meta_ads.py` (`_create_ctwa_creative`).
- Harness com manifest de carrossel + casos de borda.
- Resolução do gate R-CAR (research/architect) antes da camada de criação.

### OUT
- Credenciais Meta Ads (Fernando) — modo real só com elas; story fecha com dry-run/mocks.
- Deploy do agente Caio na VPS.
- Scheduling do inbox (story-058).

---

## Dependências
- **Bloqueante p/ a camada de criação (AC-4/AC-5):** R-CAR resolvido ([NEEDS VERIFICATION] do `object_story_spec` de carrossel CTWA).
- **Não-bloqueante:** credenciais Meta (só go-live real).
- Reusa o parser/translate da story-039 (estende, não reescreve).

## Notas técnicas (dev)
- Manter `AdSpec.format` normalizando `static→image`; carrossel exige `cards`, os demais exigem `asset` (validação condicional por formato).
- Atenção à retrocompat: manifests image/video existentes não podem quebrar.
- Estação Windows sem Python → harnesses no WSL.

## CodeRabbit / QA
- Tipo: Feature/Refactor. Foco: validação condicional por formato, retrocompat, correção do `object_story_spec`. CodeRabbit WAIVED se não provisionado.

## Test Strategy
- Harness: carrossel válido → multi-card; <2 cards rejeitado; asset de card faltante rejeitado; image/video sem regressão. Smoke offline (sem credenciais).
