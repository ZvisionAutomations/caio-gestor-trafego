# Runbook — Deploy do agente Caio na VPS Raiz Vital (story-062)

> **Pré-requisito (gate externo):** credenciais Meta (App ID/Secret, Access Token c/
> `ads_management`+`ads_read`, Account `act_`), `page_id`, número WhatsApp vinculado à
> página, e tetos de budget. Sem elas, o Caio só roda em **dry-run** (não sobe campanha real).
> O agente **funciona** sem isso (boot, scheduler, inbox dry-run, trava de escala), mas não cria anúncios.

## Artefatos (no repo `caio-gestor-trafego`)
- `Dockerfile` — imagem do agente (python:3.11-slim, roda `python -m agent.main`).
- `docker-compose.caio.yml` — serviço `caio`, volumes `inbox/` e `logs/`, rede externa `zwaf_default`.
- `config/.env.example` — todas as variáveis (Meta, LLM, Evolution, Business Signal).
- `.dockerignore` — mantém segredos fora da imagem.

## Passo a passo (deploy-por-cópia, EC2 Instance Connect — mesmo padrão do zwaf)

1. **Empacotar e copiar** o `caio-trafego` para a VPS (ex. `/opt/caio`) via `scp`
   (chave efêmera EC2 Instance Connect; IP admin já liberado no SG).
2. **Criar `/opt/caio/.env.caio`** com os valores reais (operador, via `nano` — **nunca no chat**):
   - `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN`, `META_ACCOUNT_ID`
   - `OPENROUTER_API_KEY`
   - `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `WHATSAPP_GROUP_ID`
   - `CAIO_INBOUND_WEBHOOK_SECRET` (secret do webhook; enviar no header `x-caio-webhook-secret`)
   - `CAIO_DATABASE_URL`, `CAIO_SIGNAL_TENANT_ID` (ver passo 3)
3. **Senha do role `caio_ro`** no Postgres do zwaf (uma vez):
   ```
   docker exec -it zwaf-postgres-1 psql -U zwaf -d zwaf_raiz_vital
   ALTER ROLE caio_ro PASSWORD '<openssl rand -base64 32>';
   ```
   Depois montar `CAIO_DATABASE_URL=postgresql://caio_ro:<senha>@zwaf-postgres-1:5432/zwaf_raiz_vital`
   e `CAIO_SIGNAL_TENANT_ID=livia-raiz-vital` no `.env.caio`.
4. **Tetos de budget** em `config/settings.yaml` (`budget.max_daily_per_adset`,
   `max_daily_account_spend`, `max_new_adsets_per_day`, `max_duplications_per_adset_per_day`).
   Enquanto `max_*_per_day=0`, a duplicação autônoma fica **bloqueada** (seguro).
5. **Confirmar a rede** do zwaf: `docker network ls | grep zwaf` → ajustar `name:` em
   `docker-compose.caio.yml` se não for `zwaf_default`.
6. **Subir:**
   ```
   cd /opt/caio
   docker compose -f docker-compose.caio.yml --env-file .env.caio up -d --build
   docker logs -f caio-trafego   # validar boot + scheduler + jobs registrados
   ```
7. **Pasta de handoff:** depositar pacotes em `/opt/caio/inbox/<pasta>/` (ver
   `docs/handoff-folder-contract.md`). Manter `inbox.dry_run=true` no settings até validar.
8. **Webhook Evolution inbound (Story 070):** configurar a instancia `caio-trafego` para enviar
   `MESSAGES_UPSERT` para `http://caio-trafego:8010/inbound` na rede `zwaf_default`, com header
   `x-caio-webhook-secret` igual ao `CAIO_INBOUND_WEBHOOK_SECRET`. O handler responde apenas ao grupo
   Raiz Vital e ignora `fromMe=true`.

## Go-live check (com conta Meta real)
- Confirmar o CTA Click-to-WhatsApp (`WHATSAPP_MESSAGE` vs `SEND_MESSAGE`) — ver
  `docs/research/ctwa-api-requirements.md`.
- Primeiro upload em PAUSED + revisar no Gerenciador antes de ativar.
- Trocar `inbox.dry_run` para `false` só após o primeiro pacote validado.

## Rollback
- `docker compose -f docker-compose.caio.yml down` (o Caio é stateless; histórico em `logs/`).
- Nenhum efeito no zwaf/Lívia (serviço isolado; só leitura read-only do Postgres).
