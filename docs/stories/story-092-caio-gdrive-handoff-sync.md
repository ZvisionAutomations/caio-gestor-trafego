# Story 092 — GDrive sync do handoff de criativos [Fase 1]

> ⚠️ **RE-FATIADA no runtime Hermes (2026-07-05) — ver `hermes-v2-slicing.md` §3.** Esta story assume `inbox_poller.py` (Python legado) que o Hermes NÃO herda. Split em:
> - **092a** = rclone sync (infra) — as ACs abaixo VALEM (é infra pura, independe do runtime).
> - **092b** = tool MCP custom `upload_creative_from_inbox` (NOVA) — consome o que o rclone traz e sobe pro Meta com idempotência (`.caio_processed`). Mora no wrapper `meta-ads-mcp-guarded`. Substitui o papel do `inbox_poller.py`.
> AC-4 abaixo (`inbox_poller.py` sem mudança) é **substituída** pela 092b.

**Status:** Ready (validada @product-lead / G3 — 2026-07-04) · bloqueio externo de deploy: config rclone/GDrive
**Epic:** Caio/Hermes v2 Upgrade (Raiz Vital)
**Track:** Standard (infra)
**Fonte:** `packages/caio-trafego/docs/caio-v2-upgrade-master.md` §6.1
**Package:** caio-trafego (infra)

## Story Statement
**As** operador, **I want** deixar os criativos numa pasta organizada do Google Drive e o Caio sincronizar automaticamente pra pasta local que ele já monitora, **so that** eu solte os anúncios num lugar prático sem tocar na VPS, e o Caio suba sozinho.

## Contexto
Decisão @architect: **rclone sync cron** (opção D) vence FUSE mount (frágil), GDrive API (novo módulo) e MCP (não roda em VPS). `inbox_poller.py` já monitora a pasta local com idempotência (`.caio_processed`) — só a origem dos arquivos muda. Zero código Python novo.

## Acceptance Criteria
- **AC-1** `infra/gdrive-sync.service` + `infra/gdrive-sync.timer` (systemd) rodando `rclone copy gdrive:raiz-vital/creative-inbox /opt/caio/inbox` a cada 15 min.
- **AC-2** `rclone copy --filter "- .caio_processed"` — nunca sobrescreve o marker local de idempotência.
- **AC-3** Config rclone (`/etc/rclone/rclone.conf`, perms 600) com oauth2 refresh token; secret fora do repo.
- **AC-4** `settings.yaml` permanece `inbox.folder: "inbox"` (sem mudança de código).
- **AC-5** Runbook `docs/deploy-gdrive-sync.md`; testar `rclone copy --dry-run` antes de ativar o timer. Coexistência: operador ainda pode largar arquivo direto na pasta local.

## Escopo
- IN: unidades systemd, config rclone, runbook.
- OUT: mudança no `inbox_poller.py`; scoring de criativo (Fase 2).

## Dependências
`inbox_poller.py` (Done, story-058). Conta GDrive + pasta compartilhada.

## Complexidade
Light.

---

### Dev Agent Record — 092a (infra) — @developer 2026-07-07
**File List:**
- `packages/caio-trafego/infra/gdrive-sync.service` — **AC-1/AC-2**: `rclone copy gdrive:raiz-vital/creative-inbox /opt/caio/inbox --filter "- .caio_processed"` + log.
- `packages/caio-trafego/infra/gdrive-sync.timer` — **AC-1**: dispara a cada 15 min (`OnUnitActiveSec=15min`), `Persistent=true`.
- Runbook **AC-5** já existe: `docs/runbooks/gdrive-rclone-handoff-setup.md`.

**Completion Notes:**
- ✅ **DEPLOYADO na VPS (`srv1798729` / 187.127.44.191) 2026-07-07** via SSH (autorizado pelo dono). Timer `gdrive-sync.timer` active+enabled (15 min); 1ª sync populou `/opt/caio/inbox` (README + _template); rclone remote `gdrive` autenticado (conta `zvisionforb2b`, drive.readonly), `rclone.conf` chmod 600. E2 resolvido.
- Arquivos-fonte versionados em `packages/caio-trafego/infra/gdrive-sync.{service,timer}`.
- **AC-3** (rclone.conf perms 600) + **AC-4** (`inbox.folder: "inbox"` intocado) são passos de deploy no runbook — sem mudança de código.
- **092b** (tool `upload_creative_from_inbox` que CONSOME o inbox) é story separada — ainda a rascunhar.
