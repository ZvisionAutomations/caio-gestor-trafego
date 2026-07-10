# Decisão — Reconciliação de Runtime (item #1) — RESOLVIDO 2026-07-04

> Resolve o bloqueante #1 do `caio-v2-deploy-rollout-runbook.md`. Poupa a próxima sessão de re-descobrir isso.

## Achado
O `packages/caio-trafego/` contém DOIS mundos:
- **`agent/` (Agno/Python)** — design original (stories 017-062). `caio.py`, `meta_ads.py` (facebook-business SDK), `optimize.py`, `analyze.py`, `whatsapp.py` (Evolution). **NUNCA foi pra produção.**
- **`hermes/` (SOUL + config)** — o que **RODA em produção** na VPS Hostinger. Caio = **Hermes Agent v0.18** (gateway NousResearch) governado por `SOUL.md` + **MCP meta-ads** (40+ tools) + cron/memória nativos. Cérebro GLM-4.7-flash (OpenRouter). Decisão de 2026-06-30 (ver `SETUP-HERMES.md`).

## Decisão
**Produção é Hermes (SOUL + MCP). O `agent/` Python é legado/superado — não reanimar.** As stories v2 (087-094) foram escritas contra o Python; precisam ser **re-mapeadas pra realidade Hermes** antes de codar.

## Princípio arquitetural (chave)
- **Raciocínio + soft guardrails** → vivem no **SOUL** (prompt).
- **Enforcement determinístico** (teto financeiro, validação de ID, caps) → **NÃO pode ser prompt** (LLM não é determinístico). Vive num **wrapper/fork do `meta-ads-mcp`** que intercepta as tools mutantes antes de chamar a Graph API.
- **Thresholds** → `config.yaml`/arquivo lido pelo wrapper.

## Mapeamento das stories Fase 1 → Hermes

| Story | Escrita como | Realidade Hermes | Onde o código vive |
|---|---|---|---|
| **087 CAPI** | módulo zwaf | ✅ **VALE COMO ESTÁ** (é zwaf-side/Lívia, independe do runtime do Caio) | `zwaf/capi/` |
| **088 Guardian** | `agent/guardian.py` | Teto/circuit-breaker determinístico → **wrapper do meta-ads-mcp** + soft rules no SOUL | wrapper MCP + SOUL |
| **089 State machine** | `agent/adset_state_machine.py` | Estado persistido em DB lido pelo wrapper; transições guiadas por SOUL | sidecar/DB + SOUL |
| **090 Regras** | `optimize.py` | Thresholds em config + SOUL (raciocínio) + enforcement no wrapper | SOUL + config + wrapper |
| **091 Schema validation** | `agent/tool_validator.py` | **Wrapper do MCP** valida `adset_id` numérico antes do dispatch | wrapper MCP |
| **092 GDrive sync** | `inbox_poller.py` | rclone→pasta OK, MAS Hermes não tem inbox_poller → o **upload** precisa de **tool MCP custom** OU cron-prompt que lê a pasta e sobe | rclone + MCP custom/cron |
| **093 Retargeting** | `workflows/retargeting.py` | SOUL directive + MCP | SOUL + MCP |
| **094 Compliance** | `agent/compliance/*.py` | Lista em config + SOUL guardrail + validação no wrapper | SOUL + config + wrapper |

## Consequência prática (próxima sessão)
1. A Fase 1 vira **2 sub-tracks:**
   - **Track zwaf:** story-087 (CAPI) — segue como escrita.
   - **Track Hermes:** um **fork/wrapper do `meta-ads-mcp`** que adiciona Guardian + schema-validation + caps + hooks de state/regras, MAIS diretivas no `SOUL-v2.md` MAIS `config.yaml` de thresholds. Stories 088/089/090/091/094 colapsam nesse wrapper + SOUL.
2. **092** precisa de decisão extra: tool MCP custom de upload de criativo vs cron-prompt lendo a pasta (o Hermes não herda o `inbox_poller.py`).
3. **@architect** valida esse mapeamento e re-fatiar as stories no runtime Hermes é a 1ª tarefa. As ACs continuam válidas (o QUE); muda o ONDE.

## O que NÃO muda
- Todas as decisões de negócio/thresholds v1 (§8 do doc mestre).
- A story-087 (CAPI zwaf-side).
- O rollout seguro (warn-only, flags, backup) — só que as "flags" viram config do Hermes/wrapper, não `settings.yaml` do Python.
