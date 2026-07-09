# Story 093 — Retargeting estruturado [Fase 1]

**Status:** Ready (validada @product-lead / G3 — 2026-07-04)
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
