# Runbook — Deploy + Rollout seguro (Caio v2)

> Rollout C. Caio EM PRODUÇÃO → nada de big-bang. Executar na próxima sessão (@developer + @devops).

## ✅ Item #1 — RECONCILIAÇÃO DE RUNTIME — RESOLVIDO (2026-07-04)

> Ver **`runtime-reconciliation-decision.md`**. Resumo: produção = **Hermes (SOUL+MCP)**; `agent/` Python = legado (não reanimar). Features determinísticas (Guardian/schema/caps) → **wrapper do `meta-ads-mcp`** + diretivas no SOUL + config de thresholds. story-087 (zwaf) vale como está. 1ª tarefa da próxima sessão = @architect re-fatiar as stories nesse mapeamento. O texto abaixo fica como histórico da questão.

## (histórico) Reconciliação de runtime — a questão
As stories 087-094 foram escritas contra `packages/caio-trafego` (Agno/Python: `optimize.py`, `meta_ads.py`, `analyze.py`, `spend_gate.py`...). **Mas a produção na VPS Hostinger roda o `Hermes Agent v0.18`** (runtime diferente, GLM-4.7-flash via OpenRouter, SOUL + MCP meta-ads) — o `caio-trafego` (Docker, story-062) **nunca foi deployado**.
**Decidir com @architect/@developer:**
- (a) Deployar finalmente o `caio-trafego` como o Caio v2 (substituindo o Hermes stopgap)? → as stories valem como estão.
- (b) Implementar as features v2 no runtime **Hermes**? → as stories precisam ser re-mapeadas pro codebase do Hermes (Guardian/state machine/CAPI/validation viram módulos/SOUL do Hermes).
> Sem essa decisão, a implementação trava. É o primeiro ponto da próxima sessão.

## Passo 1 — Backup pré-deploy (SEMPRE)
```bash
systemctl stop hermes-gateway
mkdir -p /opt/backups
tar czf /opt/backups/pre-caio-v2-$(date +%Y%m%d-%H%M%S).tgz /opt/caio /root/.hermes 2>/dev/null
# DB (schema + tabelas novas):
pg_dump --schema-only "$CAIO_DATABASE_URL" > /opt/backups/schema-pre-caio-v2-$(date +%Y%m%d).sql
```
⚠️ Confirmar caminhos reais (`/opt/caio`, `/root/.hermes`) e a `CAIO_DATABASE_URL` na VPS.

## Passo 2 — Feature flags (settings.yaml / config do runtime escolhido)
Cada componente entra desligado/observador e liga individualmente:
```yaml
guardian:   { enabled: true, mode: warn, base_daily_cap: 300, reinvest_pct: 0.20 }
state_machine: { enabled: true, persist: false }   # persist=false = fallback in-memory
rules:      { multicondition: false }              # liga após validar Guardian
capi:       { enabled: false }                     # liga após secrets Meta + test event
retargeting:{ enabled: false }
compliance: { enabled: true }                       # lista de proibidos sempre on
```

## Passo 3 — Ordem de rollout (com observação entre etapas)
1. **088 Guardian** em `mode: warn` (só alerta) + **089 state machine** `persist: false` → **observar 7 dias**.
2. Ligar `CAIO_DATABASE_URL` → `state_machine.persist: true`; conferir tabela `caio_adset_state`.
3. `guardian.mode: block` após validar thresholds com Fernando/Kauê.
4. **087 CAPI**: secrets Meta + **test event** OK → `capi.enabled: true` (Purchase + InitiateCheckout proxy).
5. **090 regras** `multicondition: true` (agora com sinal de atribuição do CAPI).
6. **092 GDrive sync** (runbook próprio) · **094 compliance** · **093 retargeting** `enabled: true`.

## Passo 4 — Health check após CADA etapa
- Endpoint de saúde → 200
- Suíte de harnesses do runtime → verde
- Cron/ciclo roda sem erro + Guardian não bloqueia falso-positivo

## Passo 5 — Rollback (por componente)
- Flip da feature flag → off (reverte sem redeploy).
- Se preciso: `systemctl stop <svc>` → restaurar `tar`/`pg_restore` do backup → `systemctl start`.
- **Nunca** `--force` em nada de produção sem confirmação.

## Checklist de saída
- [ ] Item #1 (runtime) decidido com @architect
- [ ] Backup pré-deploy validado (arquivo existe + restaurável)
- [ ] Feature flags no config do runtime escolhido
- [ ] Ordem de rollout acordada
- [ ] Rollback testado (flip de flag reverte)
