# Runbook — GDrive + rclone (handoff de criativos)

> **Bloqueio B** da story 092. Conta: **`zvisionforb2b`** (DECIDIDO — a pasta vive no Drive local do Miguel, é onde os criativos do Synapse são gerados; mais prático que uma conta separada). Executar na próxima sessão (com @developer/@devops).
> Caio só LÊ os criativos → escopo `drive.readonly` basta. Secret em `/etc/rclone/rclone.conf` (perms 600).

## Passo 1 — Pasta no Drive (conta zvisionforb2b) — ✅ PRONTA
✅ **JÁ CRIADA (2026-07-04)** em `G:/Meu Drive/raiz-vital/creative-inbox/` (conta `zvisionforb2b`) com `README.md` + `_template/manifest.yaml`. **Conta confirmada (2026-07-05):** mantém-se na `zvisionforb2b` — é onde os criativos gerados pelo Synapse já caem localmente; o rclone (passo 3) autentica nessa conta. Sem mudança pendente.

Estrutura criada:
```
raiz-vital/creative-inbox/
  <campanha>/manifest.yaml
  <campanha>/<assets...>
```
Convenção = a mesma do `handoff-folder-contract.md` (story-061). Um subfolder por pacote/campanha.

## Passo 2 — Instalar rclone na VPS
```bash
curl https://rclone.org/install.sh | sudo bash
rclone version
```

## Passo 3 — Configurar remote `gdrive` (oauth headless)
VPS é headless → oauth via máquina com browser:
1. Numa máquina local com rclone: `rclone authorize "drive"` → autentica com a **conta Google da Raiz Vital** → copia o JSON do token.
2. Na VPS: `rclone config` → `n` (novo) → nome `gdrive` → storage `drive` → `client_id/secret` em branco (ou próprio, p/ mais quota) → **scope: `2` (drive.readonly)** → `config_token` = colar o JSON do passo 1.
   → **Conta a autenticar: `zvisionforb2b` (a mesma onde a pasta já vive).**
3. Testar: `rclone lsd gdrive:raiz-vital/creative-inbox`
4. Proteger: `chmod 600 /etc/rclone/rclone.conf` (ou `~/.config/rclone/rclone.conf` do user do serviço).

## Passo 4 — systemd service + timer (15 min)
`/etc/systemd/system/gdrive-sync.service`:
```ini
[Unit]
Description=Sync criativos GDrive -> Caio inbox
[Service]
Type=oneshot
ExecStart=/usr/bin/rclone copy gdrive:raiz-vital/creative-inbox /opt/caio/inbox --filter "- .caio_processed" --log-file /var/log/gdrive-sync.log --log-level INFO
```
`/etc/systemd/system/gdrive-sync.timer`:
```ini
[Unit]
Description=Roda gdrive-sync a cada 15 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
[Install]
WantedBy=timers.target
```
⚠️ `--filter "- .caio_processed"` = nunca sobrescreve o marker de idempotência local.
⚠️ Confirmar o caminho real do inbox na VPS (`/opt/caio/inbox` é premissa — validar contra o `settings.yaml`/deploy real).

## Passo 5 — Dry-run + ativar
```bash
rclone copy gdrive:raiz-vital/creative-inbox /opt/caio/inbox --filter "- .caio_processed" --dry-run
systemctl daemon-reload && systemctl enable --now gdrive-sync.timer
systemctl list-timers | grep gdrive
```

## Checklist de saída
- [x] Pasta `raiz-vital/creative-inbox` criada no Drive (conta `zvisionforb2b`) — 2026-07-04
- [ ] rclone instalado + remote `gdrive` (readonly) autenticado
- [ ] `rclone lsd` lista a pasta
- [ ] service+timer criados, dry-run OK, timer ativo
- [ ] rclone.conf perms 600
