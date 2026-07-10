# Runbook — Sequência de Deploy VPS-ready (Caio v2 · Fase 1)

> **Executor:** OWNER via SSH (`ssh -i C:\temp\hostinger\rv_hostinger root@187.127.44.191`).
> **Autoria:** @devops (Pipeline) — 2026-07-09. Adapta o `caio-v2-deploy-rollout-runbook.md` (2026-07-04) ao que foi implementado **depois** dele (087 CAPI, 090 regras, 091 schema, 092b upload, 093 retargeting, migrations 013/014, wrapper Node).
> **Regra:** nada de big-bang — cada componente entra em `warn`/observador e só depois vira `enforce`. Rollback por etapa.
> 🔐 = ponto onde o owner cola um segredo manualmente (NUNCA no chat/commit).
> [NEEDS VERIFICATION] = confirmar ao vivo na VPS antes de prosseguir.

---

## 0. Fatos de infra (verificados no código, não assumir)

| Item | Valor real |
|---|---|
| zwaf | `/opt/zwaf` · `docker compose ... --env-file .env.raiz-vital` · banco `zwaf_raiz_vital` |
| Hermes | systemd `hermes-gateway.service` (root, home `/root/.hermes`) · MCP hoje = `uvx meta-ads-mcp` (conta `act_1745516809747438`) |
| Wrapper (novo) | vendorizado no repo `caio-gestor-trafego` → clonar em `/opt/caio/caio-gestor-trafego` → wrapper em `.../meta-ads-mcp-guarded` |
| Inbox (092a) | `/opt/caio/inbox` (rclone já rodando) |
| **CAPI envs** | `ZWAF_CAPI_DATASET_ID`, `ZWAF_CAPI_TOKEN`, `ZWAF_CAPI_ACTION_SOURCE`, `ZWAF_CAPI_API_VERSION`, `ZWAF_CAPI_TEST_EVENT_CODE` — no `.env.raiz-vital` do zwaf |
| **CAPI DB** | reusa o `DATABASE_URL` do zwaf (lookup `lead_attribution` + `capi_dispatch_log`) — **nenhuma URL nova** |
| **Wrapper DB** | `CAIO_DATABASE_URL` **única** faz LEITURA de estado (089) e **ESCRITA** no ledger (092b/093) → tem que ser role com `INSERT/UPDATE` em `caio_upload_ledger` |

> ⚠️ Correção vs. briefing: **não existe** `CAIO_DB_WRITE_URL` no código. O wrapper usa só `CAIO_DATABASE_URL`.

### Gotchas duráveis (do doc mestre Hostinger)
- `.env` com `$` no valor (ex.: token) → docker compose expande → **escapar `$`→`$$`** no `.env.raiz-vital`. (O `hermes-gateway` roda via systemd, **não** compose → ali o `$` é literal; **não** escapar no env do Hermes.)
- Migrations `*_rollback.sql` **nunca** no dir de initdb (rodam no boot). Aplicar rollback só manualmente.
- `.env` em CRLF vira role `zwaf\r` → normalizar `sed -i 's/\r$//' <arquivo>`.
- **NUNCA** usar o one-click Hermes da Hostinger (é reimagem → apaga a Lívia).

---

## 1. Backup pré-deploy (SEMPRE)

```bash
# 1.1 — parar só o Hermes (zwaf/Lívia seguem no ar; o deploy do zwaf é isolado no passo 5)
systemctl stop hermes-gateway

# 1.2 — snapshot de arquivos do Caio/Hermes
mkdir -p /opt/backups
tar czf /opt/backups/pre-caio-v2-$(date +%Y%m%d-%H%M%S).tgz \
  /opt/caio /root/.hermes 2>/dev/null

# 1.3 — dump do schema + dados das tabelas do Caio ANTES das migrations
#        (descobrir a connection string do zwaf; NÃO imprimir a senha)
docker compose -f /opt/zwaf/docker-compose.client.yml --env-file /opt/zwaf/.env.raiz-vital \
  exec -T postgres pg_dump -U postgres -d zwaf_raiz_vital \
  > /opt/backups/zwaf_raiz_vital-pre-caio-v2-$(date +%Y%m%d-%H%M%S).sql
```
✅ **Checkpoint:** os 3 arquivos existem em `/opt/backups` e o `.sql` não está vazio (`ls -lh /opt/backups`).

---

## 2. Migrations (EM ORDEM, no banco `zwaf_raiz_vital`)

> Todas as tabelas do Caio (`caio_adset_state`, `capi_dispatch_log`, `caio_upload_ledger`) vivem no mesmo Postgres do zwaf. Aplicar via `psql` no container, **na ordem** 012 → 013 → 014.

> ⚠️ **Precondição:** os arquivos 013/014 entraram no zwaf no commit `39d29e1` (branch `caio/feat/story-087-capi`, já mergeada). O `/opt/zwaf` na VPS precisa estar puxado pra um commit que os contenha **antes** deste passo:
> ```bash
> cd /opt/zwaf && git fetch && git log --oneline -1 -- infra/migrations/014_caio_upload_ledger.sql
> #   → se vazio, fazer git pull/checkout do branch/commit que tem as migrations (ex.: main pós-merge do 087)
> ```

```bash
cd /opt/zwaf
PSQL() { docker compose -f docker-compose.client.yml --env-file .env.raiz-vital \
  exec -T postgres psql -U postgres -d zwaf_raiz_vital "$@"; }

# 2.1 — 012 já foi aplicada? (caio_adset_state)
PSQL -c "SELECT to_regclass('public.caio_adset_state');"
#   → se retornar NULL, aplicar 012 ANTES:
PSQL < packages/zwaf/infra/migrations/012_caio_adset_state.sql   # só se faltar

# 2.2 — 013 capi_dispatch_log (087). Idempotente (CREATE TABLE IF NOT EXISTS).
PSQL < packages/zwaf/infra/migrations/013_capi_dispatch_log.sql

# 2.3 — 014 caio_upload_ledger (092b/093). Idempotente + GRANT a caio_rw se existir.
PSQL < packages/zwaf/infra/migrations/014_caio_upload_ledger.sql
```
> ⚠️ Caminho dos arquivos: se o repo do zwaf na VPS estiver em `/opt/zwaf` mas os migrations não, ajustar o path (`find / -name 013_capi_dispatch_log.sql 2>/dev/null`). O `< arquivo` lê do host, o `psql` roda no container — funciona porque o `exec -T` recebe o stdin.

✅ **Checkpoint:**
```bash
PSQL -c "SELECT to_regclass('public.capi_dispatch_log'), to_regclass('public.caio_upload_ledger');"
# ambas não-NULL. E a role do CAIO_DATABASE_URL precisa escrever no ledger:
PSQL -c "\dp caio_upload_ledger"   # confirmar INSERT/UPDATE pra role do wrapper (caio_rw)
```
🔐 Se a role do `CAIO_DATABASE_URL` **não** for `caio_rw`, conceder à role real:
`PSQL -c "GRANT SELECT,INSERT,UPDATE ON caio_upload_ledger TO <role_do_wrapper>;"`

**Rollback do passo 2:** `PSQL < packages/zwaf/infra/migrations/014_caio_upload_ledger_rollback.sql` e `013_..._rollback.sql` (na ordem inversa).

---

## 3. Wrapper `meta-ads-mcp-guarded` (npm install)

> O wrapper é o novo runtime determinístico (091/088/089/090/092b/093/094). Vendorizado no repo `caio-gestor-trafego` → chega na VPS por git.

```bash
# 3.1 — trazer o repo caio-gestor-trafego (o wrapper está vendorizado nele)
cd /opt/caio/caio-gestor-trafego 2>/dev/null && git pull \
  || git clone https://github.com/ZvisionAutomations/caio-gestor-trafego.git /opt/caio/caio-gestor-trafego

# 3.2 — instalar deps do wrapper (Linux resolve o yaml que o GDrive corrompe; aqui é limpo)
cd /opt/caio/caio-gestor-trafego/meta-ads-mcp-guarded
npm install --omit=dev

# 3.3 — smoke local: parseia e sobe stdio sem crashar
node --check src/index.js && echo "syntax OK"
node --test 2>&1 | tail -5   # suíte do wrapper deve passar verde no Linux
```
✅ **Checkpoint:** `npm install` sem erro, `node --check` OK, testes verdes.

---

## 4. Apontar o Hermes pro wrapper (troca do MCP) + envs

> Hoje o Hermes chama `uvx meta-ads-mcp` direto. Passa a chamar o **wrapper**, que spawna o `meta-ads-mcp` real como filho (passthrough) e intercepta os mutantes.

**4.1 — Localizar a config do MCP do Hermes** [NEEDS VERIFICATION do formato exato]:
```bash
grep -rn "meta-ads-mcp" /root/.hermes/ 2>/dev/null   # achar onde o MCP está declarado
```

**4.2 — Trocar a entrada do MCP `meta-ads`** de:
```
command: /root/.hermes/bin/uvx   args: ["meta-ads-mcp"]
```
para (referência pronta no repo: **`hermes/mcp-meta-ads-guarded.example.json`**; mantendo as envs Meta que já existem — `META_ACCESS_TOKEN`/`META_AD_ACCOUNT_ID`):
```
command: node
args:    ["/opt/caio/caio-gestor-trafego/meta-ads-mcp-guarded/src/index.js"]
env:
  GUARDED_CHILD_COMMAND: /root/.hermes/bin/uvx
  GUARDED_CHILD_ARGS_JSON: '["meta-ads-mcp"]'     # o wrapper spawna o filho real
  GUARDED_CONFIG_PATH:  /opt/caio/caio-gestor-trafego/hermes/guardrails.yaml
  CAIO_INBOX_DIR:       /opt/caio/inbox
  CAIO_DATABASE_URL:    <role com escrita no ledger>       # 🔐 mesma do state 089
  # herdar META_ACCESS_TOKEN / META_AD_ACCOUNT_ID já configurados no Hermes
```

**4.3 — Confirmar o `guardrails.yaml`** (já vem no clone, mesmo repo do wrapper):
```bash
grep -E "^  mode:|^guardian:|^retargeting:" /opt/caio/caio-gestor-trafego/hermes/guardrails.yaml   # deve começar em warn
```
> Se `GUARDED_CONFIG_PATH` não existir/ilegível, o wrapper cai em **DEFAULTS seguros** (guardian `warn`, cap R$300) — não derruba o boot, mas os thresholds do arquivo não valem. Confirmar o path.

**4.4 — Reiniciar e validar o passthrough:**
```bash
systemctl start hermes-gateway
systemctl status hermes-gateway --no-pager | head -15
journalctl -u hermes-gateway -n 40 --no-pager | grep -i "guarded\|filho conectado\|guardian="
```
✅ **Checkpoint (tools/list):** o Hermes deve enxergar as tools do `meta-ads-mcp` **+** `upload_creative_from_inbox` **+** `build_retargeting_campaign`. Confirmar via um ciclo de teste do Hermes ou log `[guarded] proxy pronto`.

🚩 **[NEEDS VERIFICATION] — assinaturas reais das tools do filho.** Os arg-shapes de `create_campaign/create_adset/upload_ad_image/create_ad_creative/create_ad` (092b) e `create_custom_audience` (093) seguem a Graph API mas só confirmam ao vivo. Rodar **1 pacote de teste** em pasta isolada do inbox e conferir no log se algum passo volta erro de argumento; ajustar `buildSteps`/`buildRetargetingSteps` se divergir **antes** de soltar em produção.

**Rollback do passo 4:** reverter a entrada do MCP pro `uvx meta-ads-mcp` original e `systemctl restart hermes-gateway`.

---

## 5. Secrets CAPI (087) no zwaf + smoke Test Event

> O dispatcher é **best-effort**: sem `ZWAF_CAPI_DATASET_ID`/`ZWAF_CAPI_TOKEN` ele **no-opa** (não quebra venda). Ou seja: CAPI fica "desligado" enquanto os secrets estão vazios. Ligar = preencher.

**5.1 — Decisão de action_source** (do `meta-capi-setup-guide.md`):
- Número WABA **oficial**? → `ZWAF_CAPI_ACTION_SOURCE=business_messaging` (default).
- Número Evolution/Baileys (caso Raiz Vital hoje)? → **fallback** `ZWAF_CAPI_ACTION_SOURCE=other` (dataset da conta de anúncios + `ctwa_clid` em `custom_data`).

**5.2 — Editar `.env.raiz-vital` (começar com Test Event pra não sujar produção):**
```bash
nano /opt/zwaf/.env.raiz-vital
```
🔐 adicionar (valores com o owner — NÃO colar aqui):
```
ZWAF_CAPI_DATASET_ID=...            # 🔐
ZWAF_CAPI_TOKEN=...                 # 🔐  (se tiver '$', escapar $→$$ — é lido via compose)
ZWAF_CAPI_ACTION_SOURCE=other       # ou business_messaging (ver 5.1)
ZWAF_CAPI_API_VERSION=v21.0
ZWAF_CAPI_TEST_EVENT_CODE=TEST12345 # 🔐  provisório p/ o smoke; REMOVER depois
```
```bash
sed -i 's/\r$//' /opt/zwaf/.env.raiz-vital    # gotcha CRLF
```

**5.3 — Recarregar o zwaf (sem rebuild se só mudou env):**
```bash
cd /opt/zwaf
docker compose -f docker-compose.client.yml -f docker-compose.https.yml \
  --env-file .env.raiz-vital up -d
```

**5.4 — Smoke Test Event** (EMQ ≥ 7):
- Disparar 1 Pix de teste (InitiateCheckout) e/ou confirmar 1 pagamento de teste (Purchase) num lead que tenha `ctwa_clid` em `lead_attribution`.
- Conferir no **Events Manager → Test Events** (com o `TEST_EVENT_CODE`) que o evento chega com `user_data.ph` (hash) + `ctwa_clid` e **EMQ ≥ 7**.
- Log sem PII:
```bash
PSQL -c "SELECT event_name,status,http_status,has_ctwa,created_at FROM capi_dispatch_log ORDER BY created_at DESC LIMIT 5;"
```
✅ **Checkpoint:** evento aparece no Test Events, `status=ok`, `has_ctwa=true`, EMQ ≥ 7.

**5.5 — Promover pra produção:** remover `ZWAF_CAPI_TEST_EVENT_CODE` do `.env.raiz-vital` → `up -d` de novo. A partir daí os eventos são reais.

**Rollback do passo 5:** esvaziar `ZWAF_CAPI_DATASET_ID`/`ZWAF_CAPI_TOKEN` (volta a no-opar) → `up -d`.

---

## 6. Rollout faseado — flag×config reconciliado

> O runbook antigo falava em flags `capi.enabled`/`retargeting.enabled`. **Elas não existem** desse jeito. Mapa real dos controles:

| Componente | Runbook antigo | Controle REAL |
|---|---|---|
| 088 Guardian | `mode: warn→block` | `guardrails.yaml → guardian.mode: warn\|enforce` (sempre carregado) |
| 089 State | `persist: false→true` | persiste quando **`CAIO_DATABASE_URL` está setado** (passo 4); `state.mode: warn\|enforce` |
| 094 Compliance | `enabled` | `guardrails.yaml → compliance.mode: warn\|enforce` (lista sempre on) |
| 090 Regras | `multicondition: true` | **sem flag** — é o reconciler cron (lê insights → escreve `caio_adset_state`) + diretiva no `SOUL-v2` mandando consultar as regras. Sem sinal de receita CAPI → só teto base (por design) |
| 087 CAPI | `capi.enabled` | **secrets no zwaf** (passo 5). Vazio = off |
| 093 Retargeting | `retargeting.enabled` | **sem flag** — é a tool `build_retargeting_campaign` que o SOUL/operador invoca. Config só tem thresholds |

**Ordem recomendada (observando entre etapas):**
1. **Semana 0:** guardian/state/compliance em **`warn`** (default do `guardrails.yaml`). Observar `caio_guardian_log` — o que *teria* bloqueado. CAPI já pode ligar (passo 5) porque é ortogonal ao enforce.
2. **Validar thresholds** com Fernando/Kauê nos logs warn.
3. **Flip pra `enforce`** — editar `guardrails.yaml`:
   ```bash
   nano /opt/caio/caio-gestor-trafego/hermes/guardrails.yaml   # guardian.mode: enforce · state.mode: enforce · compliance.mode: enforce
   systemctl restart hermes-gateway
   ```
4. **090 regras multicondição:** confirmar o reconciler cron rodando + diretiva no `SOUL-v2` (ver pendência das stories 090/093). Só então o Caio age por regra composta.
5. **093 retargeting:** rodar `build_retargeting_campaign` num pacote com criativo marcado `audience: retargeting`; começa tudo em PAUSED (owner revisa antes de ativar).

---

## 7. Health check após CADA etapa

```bash
# Hermes vivo + sem loop de restart
systemctl status hermes-gateway --no-pager | head -8
journalctl -u hermes-gateway -n 30 --no-pager | grep -i "error\|bloqueada\|guardian="

# zwaf saudável
curl -fsS https://api.raizvitaloficial.com.br/health || echo "zwaf health FALHOU"

# Guardian não está bloqueando falso-positivo (modo warn deve só logar)
PSQL -c "SELECT COUNT(*) FROM caio_guardian_log WHERE created_at > NOW() - INTERVAL '1 hour';" 2>/dev/null || true
```
✅ Cada etapa: health 200 · Hermes sem restart · Guardian sem falso-bloqueio.

---

## 8. Rollback (por componente — sempre reversível)

| Falhou em | Reverter |
|---|---|
| Migration (2) | `PSQL < ..._rollback.sql` na ordem inversa (014 → 013) |
| Wrapper (3/4) | reverter entrada MCP pro `uvx meta-ads-mcp` + `systemctl restart hermes-gateway` |
| CAPI (5) | esvaziar `ZWAF_CAPI_*` secrets → `docker compose up -d` |
| Enforce agressivo (6) | `mode: enforce → warn` no `guardrails.yaml` + restart (flip reverte sem redeploy) |
| Catástrofe | `systemctl stop hermes-gateway` → `tar xzf /opt/backups/pre-caio-v2-*.tgz -C /` → `pg_restore`/`psql < backup.sql` → restart |

> **Nunca** `--force` em nada de produção sem confirmação do owner.

---

## Checklist de saída
- [ ] Backup (1) validado — 3 arquivos, `.sql` não-vazio
- [ ] Migrations 012?/013/014 aplicadas + ledger com GRANT de escrita (2)
- [ ] Wrapper `npm install` + testes verdes (3)
- [ ] Hermes aponta pro wrapper · tools/list mostra as 2 tools novas · passthrough OK (4)
- [ ] [NEEDS VERIFICATION] assinaturas reais das tools confirmadas com 1 pacote de teste (4)
- [ ] Secrets CAPI + smoke Test Event EMQ ≥ 7 (5) → `TEST_EVENT_CODE` removido
- [ ] Rollout em `warn` observado → `enforce` após validar thresholds (6)
- [ ] Health 200 em cada etapa (7) · rollback testado (8)
```
