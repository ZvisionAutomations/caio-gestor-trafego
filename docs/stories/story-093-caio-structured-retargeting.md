# Story 093 — Retargeting estruturado [Fase 1]

**Status:** Ready for Review (implementada @developer — 2026-07-09). Pendente: `npm install` do wrapper na VPS + verificar assinaturas reais das tools de audiência (`create_custom_audience`) do meta-ads-mcp.
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §5.2, §5.5
**Package:** caio-trafego

## Story Statement
**As** gestor de tráfego, **I want** um adset de retargeting para quem iniciou conversa e não comprou, **so that** eu capture o público de maior intenção disponível — que tende ao melhor ROAS da conta.

## Contexto
Brainstorm paid media apontou o retargeting como a maior oportunidade não endereçada. Público = conversas iniciadas sem compra (últimos 14d via Business Messaging). Criativos diferenciados (prova social pesada, urgência, oferta de entrada).

## Acceptance Criteria
- **AC-1** `agent/workflows/retargeting.py` cria/gerencia Campanha 2 (Retargeting, ABO) com Adset C = conversas iniciadas sem compra 14d, budget R$30-50/dia.
- **AC-2** Estrutura de conta ABO consolidada documentada e aplicável: Campanha 1 (ToF broad) + Campanha 2 (retargeting); orçamento de entrada ~R$130-150/dia.
- **AC-3** O adset de retargeting consome criativos marcados como retargeting no manifest da pasta de handoff (prova social/urgência).
- **AC-4** Verificação de overlap ≥20% de diferenciação entre adsets da mesma campanha antes de lançar.
- **AC-5** Sujeito aos mesmos guardrails (Guardian story-088 + regras story-090).

## Escopo
- IN: workflow de retargeting, estrutura ABO, consumo de criativos segmentados.
- OUT: geração de criativo (Higgsfield/humano); lookalike (só após 100+ purchases).

## Dependências
story-087 (sinal de conversa/compra p/ montar público), story-090 (regras).

## Complexidade
Medium.

## Dev Agent Record

**Agent:** Pixel (@developer) · **Data:** 2026-07-09 · **Runtime:** Node ESM (`meta-ads-mcp-guarded`)

> ⚠️ **Desvio de runtime (mesma decisão de 090/092b):** a story escreve `agent/workflows/retargeting.py`, mas o runtime v2 do Caio é o wrapper Node + Hermes/SOUL (o `optimize.py`/poller Python foi aposentado). Implementado como módulo Node `src/retargeting.js`, config-driven, na mesma linha de `rules.js` (090) e `upload_inbox.js` (092b). A execução flui pela pipeline guardada (`callGuardedTool` → 091/088/094), satisfazendo AC-5 sem reimplementar o Guardian.

### File List
- `packages/meta-ads-mcp-guarded/src/retargeting.js` (novo) — `isRetargetingAd`/`filterRetargetingAds` (AC-3), `buildRetargetingAudience` (conversas 14d, AC-1), `clampRetargetingBudget` (faixa R$30-50, AC-1), `targetingSignature`/`estimateDifferentiation`/`checkOverlap` (diferenciação ≥20%, AC-4), `buildAccountStructure` (ABO ToF+Retargeting, AC-2), `buildRetargetingSteps` (cadeia campanha→audiência→adset→ads rtg), `runRetargeting` (orquestração via `callGuardedTool` + ledger opcional, AC-5).
- `packages/meta-ads-mcp-guarded/src/config.js` (alterado) — seção `retargeting` nos defaults + merge do YAML.
- `packages/caio-trafego/hermes/guardrails.yaml` (alterado) — seção `retargeting:` (números tunáveis sem redeploy).
- `packages/meta-ads-mcp-guarded/src/upload_inbox.js` (alterado) — exporta `readManifest(folder)` (read+validate+hash reusável entre 092b e 093; sem tocar na lógica de upload testada).
- `packages/meta-ads-mcp-guarded/src/index.js` (alterado) — registra a tool `build_retargeting_campaign` no `tools/list`; intercepta no `tools/call` (lê o pacote, filtra criativos rtg, roda a cadeia guardada).
- `packages/meta-ads-mcp-guarded/test/retargeting.test.js` (novo) — 13 testes.

### Completion Notes
- **AC-1** ✅ Campanha 2 ABO (sem budget de campanha) + Adset C com custom audience de conversas `audience_retention_days`d; budget do adset **clampado** na faixa R$30-50.
- **AC-2** ✅ `buildAccountStructure` documenta/retorna a estrutura consolidada: Campanha 1 (ToF broad) + Campanha 2 (retargeting), `entry_budget_brl_range` R$130-150.
- **AC-3** ✅ Só os ads marcados (`audience: retargeting` | `segment: rtg` | `retargeting: true`) entram — o resto do pacote (ToF) fica de fora. Marker no ad, não global.
- **AC-4** ✅ Gate de diferenciação (Jaccard sobre geo/idade/gênero/audiências in-ex) ≥ `min_differentiation_pct`; `runRetargeting` **bloqueia** o lançamento se algum par de adsets da campanha ficar abaixo (não chama a Graph).
- **AC-5** ✅ Cada passo passa por `callGuardedTool` (091 schema, 088 Guardian, 094 compliance); tudo criado em **PAUSED**. Idempotência opcional via `caio_upload_ledger` (reusa a migration 014 da 092b — sem migration nova).

### Testes
- **Suíte nova:** 13/13 passando.
- **Regressão:** rodei junto `upload_inbox.test.js` (12/12) e `rules.test.js` (10/10) → **35/35** no total (o novo `readManifest` não quebrou a 092b). `node --check` OK em `retargeting.js`/`config.js`/`upload_inbox.js`/`index.js`.
- **⚠️ Ambiente (idem 092b):** o mount do GDrive não faz `npm install` (`yaml` corrompido; EPERM/EBADF do Drive File Stream). Rodei num harness local em C: com `yaml` real → 35/35. Na VPS (Linux) basta `npm install`.

### Pendente para produção
1. @devops: `npm install` no `packages/meta-ads-mcp-guarded/` na VPS (compartilhado com 091/092b).
2. **Verificar assinaturas reais** das tools de audiência do `meta-ads-mcp` na VPS — em especial `create_custom_audience` (engagement/messaging, `retention_days`, exclusão de compradores) e os campos de `targeting.custom_audiences`/`excluded_custom_audiences` no `create_adset`. Os arg-shapes seguem a Graph API mas só confirmam ao vivo; ajustar `buildRetargetingAudience`/`buildRetargetingSteps` se divergir. [NEEDS VERIFICATION]
3. Popular a audiência de **compradores** p/ exclusão (`purchasers_audience_id` no config ou `campaign.purchasers_audience_id` no manifest) quando existir — sem ela o Adset C inclui conversas mas não exclui quem já comprou.
4. SOUL-v2: diretiva curta referenciando a estrutura ABO + o gate de overlap (single source of truth no config). Anotado como ajuste de prompt no deploy.

### Change Log
- 2026-07-09 — Implementação do retargeting estruturado (Campanha 2 ABO + Adset C conversas 14d, filtro de criativos rtg, gate de overlap ≥20%, cadeia guardada em PAUSED), config `retargeting`, tool `build_retargeting_campaign`, 13 testes. Status Ready → Ready for Review.
