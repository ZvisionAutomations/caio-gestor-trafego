---
id: story-019
title: Adaptar referencias Meta Ads Ratos e InsightfulPipe ao Caio Trafego
status: Ready for Review
owner: developer
created_at: 2026-05-28
---

# Story 019 - Caio Traffic Skill Adaptation

## Contexto

O Caio gestor de trafego ja opera analise, otimizacao e alertas de Meta Ads para a
Raiz Vital. A proxima evolucao e incorporar os melhores padroes de duas referencias:

- `duduesh/meta-ads-ratos`: catalogo operacional Meta Ads, setup seguro, leitura
  expandida, targeting, previews, diagnostico de pixel e guardrails de escrita.
- InsightfulPipe Marketing Claude Skills: playbooks de auditoria de conta, alocacao
  de budget, estrutura de campanha, teste criativo, launch checklist, scaling e
  performance analysis.

## Objetivo

Elevar o Caio de executor de thresholds para agente de trafego com playbooks de
auditoria, diagnostico e planejamento, mantendo guardrails de seguranca para a conta
de anuncios da Raiz Vital.

## Escopo

- Adicionar knowledge base com matriz de skills e regras operacionais.
- Expor tools adicionais de leitura/diagnostico Meta Ads:
  - preview de criativo;
  - insights com breakdowns;
  - busca/validacao/descricao/alcance de targeting;
  - listagem e diagnostico basico de pixels/datasets.
- Reforcar no prompt que criacao, ativacao, aumento de budget e delecao exigem
  aprovacao humana.
- Manter criacoes e duplicacoes em status `PAUSED`.
- Adicionar harness sem API real cobrindo a presenca das novas tools e knowledge.

## Fora de escopo

- Criar campanhas ou anuncios automaticamente.
- Deletar objetos da conta.
- Integrar MCP externo do InsightfulPipe.
- Copiar codigo de terceiros sem adaptacao ao padrao local.

## Criterios de aceite

- Story esta com status `Ready` antes do codigo.
- Caio carrega knowledge sobre Ratos/InsightfulPipe no prompt.
- `build_caio()` expoe as novas tools Meta Ads.
- As novas tools nao exigem chamadas reais em harnesses.
- Harnesses locais passam.

## Fontes analisadas

- https://github.com/duduesh/meta-ads-ratos
- https://insightfulpipe.com/marketing-claude-skills

## Dev Agent Record

### Agent Model Used

Codex / @developer (Pixel)

### Debug Log References

- `python harnesses/test_analyze.py` - PASS
- `python harnesses/test_report.py` - PASS
- `python harnesses/test_approve.py` - PASS
- `python harnesses/test_traffic_skills.py` - PASS
- `python scripts/run_harnesses.py` - PASS
- `python -m ruff check agent harnesses` - PASS
- `python -m ruff check agent/ harnesses/ scripts/` - PASS
- `python -c "from agent.tools.meta_ads import MetaAdsTool; print('meta_ads OK')"` - PASS
- `python -c "from agent.caio import build_caio; print('caio OK')"` - PASS
- `python -m mypy agent/caio.py agent/tools/meta_ads.py agent/tools/whatsapp.py agent/tools/scheduler.py agent/workflows/analyze.py agent/workflows/optimize.py agent/workflows/approve.py agent/workflows/report.py --python-version 3.11 --ignore-missing-imports --follow-imports=skip --no-incremental` - PASS
- `@quality-gate` read-only review - initial FAIL; fixes applied for activation guardrail,
  pixel SDK method, and stronger harness coverage.
- `@quality-gate` re-review - CONCERNS only for pixel fallback coverage; fallback and no-method
  tests added.
- `make test` - PASS after GNU Make was installed locally.

### Completion Notes

- Added Meta Ads read/diagnostic tools for creative previews, breakdown insights,
  targeting search/validation/description/reach/delivery estimates, and pixel diagnostics.
- Exposed the new tools through `build_caio()`.
- Removed `resume_ad` and `resume_ad_set` from autonomous agent tools; activation and
  reactivation now require approval.
- Corrected pixel listing to use `get_ads_pixels` with backwards-compatible fallback.
- Moved the Ratos/InsightfulPipe playbook into Caio's loaded knowledge directory.
- Added a no-real-API harness for Story 019 tool, knowledge, SDK-call, pixel fallback,
  and guardrail coverage.
- Added `scripts/run_harnesses.py` so tests can run on Windows without GNU Make.
- Updated `Makefile` to use `python`, the cross-platform harness runner, and a mypy command
  that completes on this Windows/Python 3.14 environment while checking Python 3.11 targets.
- Added package-local Story 019 so Documentation-First is satisfied inside `caio-trafego`.

### File List

- `agent/tools/meta_ads.py`
- `agent/caio.py`
- `agent/knowledge/marketing-skills.md`
- `harnesses/test_traffic_skills.py`
- `scripts/run_harnesses.py`
- `Makefile`
- `README.md`
- `.gitignore`
- `docs/stories/story-019-caio-traffic-skill-adaptation.md`

### Change Log

| Data | Agente | Acao |
|------|--------|------|
| 2026-05-29 | @developer (Pixel) | Implementou tools e harness da Story 019; validacao local passou; status Ready for Review |
