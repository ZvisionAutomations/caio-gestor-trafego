# Caio/Hermes v2 — Índice de Stories

> Norte de implementação. Fonte de verdade: `packages/caio-trafego/docs/caio-v2-upgrade-master.md`.
> Fase 1 criada (Draft). Fase 2 e roadmap **ainda NÃO criadas** — criar quando chegar a vez.

## Fase 1 — Fundação (segurança + sinal real) — CRIADAS (Draft)

| Story | Título | Pkg | Complexidade | Depende de |
|---|---|---|---|---|
| 087 | CAPI Business Messaging (Purchase + proxy) | zwaf | Heavy | 039, 060 |
| 088 | Guardian: circuit-breaker + hard cap | caio | Medium | settings |
| 089 | State machine de adset (persistida) | caio | Medium | CAIO_DATABASE_URL |
| 090 | Motor de regras multi-condição config-driven | caio | Medium-Heavy | 088, 089, 087 |
| 091 | Schema validation de tool calls | caio | Medium | caio.py |
| 092 | GDrive sync do handoff (rclone) | caio/infra | Light | 058 |
| 092b | Tool `upload_creative_from_inbox` (upload idempotente) | meta-ads-mcp-guarded | Medium-Heavy | 092a, 091 |
| 093 | Retargeting estruturado | caio | Medium | 087, 090 |
| 094 | Lista compliance Health/Wellness | caio | Light-Medium | — |

**Ordem sugerida de implementação (ajustada — 087 antes de 090 por causa do reinvestimento):**
`088` Guardian (segurança primeiro, ships com teto base R$300) → `089` state machine → **`087` CAPI (foundation: sem atribuição não há reinvestimento nem otimização por venda)** → `090` motor de regras (consome 087/088/089) → `091` schema validation → `092` GDrive sync → `094` compliance → `093` retargeting.

**Status de validação (@product-lead / G3 — 2026-07-04): TODAS Ready.** Ver registro de validação abaixo.
**Rollout:** Caio em produção → faseado (Guardian warn-only 7d, feature flags por componente, backup pré-deploy).
**Bloqueios externos (não impedem estar Ready, impedem o deploy):** 087/090 dependem de dataset+token Meta (CAPI); 092 depende de config rclone/GDrive.

## Registro de validação (@product-lead, G3)
Todas as 8 stories validadas contra o checklist de story-lifecycle: AC claras, escopo IN/OUT, dependências mapeadas, complexidade estimada, rastreáveis ao doc mestre (No Invention). **Veredito: PASS → Ready.** Observações: 087 (Heavy) recomenda faseamento F1-F6 na implementação; 089 requer migration (envolver @data-engineer); 087/092 têm bloqueio externo de credenciais/config antes do deploy.

## Ad-hoc — criada fora da sequência (call 2026-07-07)

| Story | Título | Pkg | Complexidade | Depende de |
|---|---|---|---|---|
| 095 | Roteamento multi-produto (destino WhatsApp + sinal por produto) | caio | Light | 092b (quando existir) |

Decisão fechada com o dono: Fernando vende AlphaPulse manualmente (sem bot) → modo assistido, sem reinvestimento automático. AC-3 (mapeamento produto→dataset) virou backlog. Pendente @product-lead validar (G3).

## Fase 2 — Qualidade de decisão + criativo — NÃO criar ainda

| ID | Título | Nota |
|---|---|---|
| (reescopo 085) | MoA advisory-only | Ensemble só scoring/recomendação, nunca execução |
| S-J | Creative scoring + score Higgsfield no manifest | Estende schema do manifest + scorer |
| S-K | Separação Orchestrator/Executor (incremental) | Refactor gradual |

## Roadmap / Backlog — NÃO criar ainda

- Calibração de undercount do `ctwa_clid` (campo manual na Lívia, primeiros 60d).
- Google Search (marca + concorrentes) — canal complementar 90d.
- Migração ABO → CBO quando volume >50 compras/sem por adset.

## Runbooks de pré-deploy (prontos — executar na próxima sessão)
- `runbooks/meta-capi-setup-guide.md` — Bloqueio A (Meta CAPI, manual, acesso Kauê/Fernando + verificação WABA/Evolution).
- `runbooks/mensagem-caue-meta-credentials.md` — **mensagem pronta pro Cauê** liberar Dataset ID + token + confirmar WABA (desbloqueia 087/090).
- `runbooks/gdrive-rclone-handoff-setup.md` — Bloqueio B (GDrive Raiz Vital + rclone na VPS).
- `runbooks/caio-v2-deploy-rollout-runbook.md` — backup + feature flags + ordem de rollout + rollback.

## ✅ Item #1 — RESOLVIDO (2026-07-05): runtime re-fatiado
Produção = **Hermes v0.18** (SOUL+MCP), não o `agent/` Python. @architect re-fatiou as 8 stories → `hermes-v2-slicing.md` (developer-ready). Colapsam em 4 artefatos: **A** wrapper `meta-ads-mcp-guarded` (088/089-enforce/090-enforce/091/092b/094-enforce), **B** `SOUL-v2.md`, **C** `config.yaml`, **D** DB sidecar `caio_adset_state`. Track zwaf (087/CAPI) segue independente.
- **092 splitada:** 092a rclone (infra, ACs valem) + **092b** tool MCP custom `upload_creative_from_inbox` (idempotente, substitui `inbox_poller.py`) — DECISÃO FECHADA (tool custom > cron-prompt).
- **Ordem re-fatiada:** `091` (funda o wrapper A) → `088` → `089` → `087` (paralelo) → `090` → `092a`→`092b` → `094` → `093`.
- ACs de negócio inalteradas; @product-lead re-valida só o *onde* → mantém Ready.
- **Revisão @architect (2026-07-05) — 5 furos corrigidos (§7 do slicing):** A) wrapper é **proxy**, não fork (spawna meta-ads-mcp real, passthrough); B) **reconciler** cron na 089 (transições temporais/métricas que não são mutação); C) **ledger** `caio_upload_ledger` na 092b (idempotência multi-passo, sem duplicar creative); D) single source of truth (números só no config, SOUL referencia); E) **decision log** `caio_guardian_log` na 088 desde dia 1 (warn-mode observável). Impacto: +1 cron, +2 tabelas, migration DB antecipada pra 088 (@data-engineer).

## Respostas do dono — v1 TRAVADO (2026-07-04)
Margem: não definida (assume 60%) · LTV: recompra frequente 60-90d (CPL R$40 piso, R$55-60 stretch) · latência: varia (piso 72h, atribuição 28d) · Higgsfield: indefinida (não matar criativo sem substituto) · autonomia: híbrida (autônomo só em adset estável ≥7d) · budget: teto R$300 + **escala por reinvestimento 20% da receita atribuída via CAPI** (dep. 087) · Google Search: não agora.
> **Aberto:** só a margem bruta real (revisar CPL-alvo quando confirmada) + cadência real do Higgsfield (risco operacional).
