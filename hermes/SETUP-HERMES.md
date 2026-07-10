# Setup do Caio no Hermes Desktop — Passo a Passo

Objetivo: colocar o Caio no ar **hoje**, conversando no Telegram da Raiz Vital, lendo e
gerenciando a conta Meta via MCP, governado pelo `SOUL.md` deste diretório.

---

## Pré-flight — RESOLVIDO ✅ (pesquisa 2026-06-30, doc oficial Hermes Desktop v0.15.2)

Confirmado pela doc oficial do NousResearch — **tudo viável nativo, sem plano B Python**:

| Capacidade | Status | Como |
|---|---|---|
| MCP custom (Meta Ads via npx) | ✅ qualquer um, sem whitelist | `hermes mcp add ...` |
| Telegram nativo em grupo | ✅ | gateway nativo, transcreve voz |
| Cron 08/14/20:30 | ✅ nativo | `hermes cron create ... --deliver telegram` |
| OpenRouter (DeepSeek, tool-calling) | ✅ | qualquer endpoint OpenAI-compatible |
| App desktop Win/Mac/Linux | ✅ | one-click install, self-update |

> Os comandos abaixo são os **reais** do CLI do Hermes. Tudo também dá pra fazer pela UI do app
> desktop (Settings), mas o CLI é mais rápido e reproduzível. Rode num terminal com o Hermes instalado.

---

## Passo 1 — Modelo (cérebro)

- Provider: **OpenRouter** (OpenAI-compatible) → base URL `https://openrouter.ai/api/v1`
- Modelo: `deepseek/deepseek-v3.2` (suporta tool-calling; reasoning integrado)
- Chave: `OPENROUTER_API_KEY` (a mesma do `.env.caio`)

```bash
# Aponta o Hermes pro OpenRouter + DeepSeek (ajuste o nome exato da flag conforme `hermes config --help`)
export OPENROUTER_API_KEY="sk-or-..."          # mesma chave do .env.caio
hermes config set provider openrouter
hermes config set model deepseek/deepseek-v3.2
hermes config set reasoning on                 # se a flag existir no seu build
```

> Pela UI: status bar → **model picker** → escolher OpenRouter / `deepseek/deepseek-v3.2`.
> No MVP, **1 modelo cérebro basta**. O split brain/muscle (Gemini Flash-Lite) é otimização de
> custo pra fase VPS — ignore agora.

## Passo 2 — Telegram (bot no grupo da Raiz Vital)

1. Fale com **@BotFather** → `/newbot` → escolha nome e username → ele devolve o **bot token**.
   Guia oficial: https://core.telegram.org/bots/features#botfather
2. Adicione o bot ao **grupo da Raiz Vital** e promova a **admin** (pra ler/responder no grupo).
   - Como o agente é do time todo (Kauê = aprovações, Fernando = operacional), deixe o bot admin
     com permissão de ler mensagens e postar.
3. Conecte no Hermes:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-..."      # token do BotFather
hermes gateway telegram start                    # sobe o gateway do Telegram
# verifique a conexão:
hermes gateway status
```

> Pela UI: Settings → Messaging → **Telegram** → colar o token → Connect.
> Group ID de referência (já conhecido): `120363429540176496`.

## Passo 3 — MCP Meta Ads (você mesmo configura — tokens estão no `mcp.json`)

Todos os IDs/tokens/secrets da conta da Raiz Vital já estão no seu `mcp.json`.

```bash
# Registra o MCP Meta Ads como tool server do Hermes
hermes mcp add meta-ads --command npx --args "-y,meta-ads-mcp"

# Passa as credenciais por env (NUNCA cole token cru no comando/arquivo versionado)
export META_ACCESS_TOKEN="..."        # do seu mcp.json
export META_AD_ACCOUNT_ID="act_..."   # conta de anúncios da Raiz Vital

# Confirma que as tools subiram:
hermes mcp list
```

- No startup o Hermes lê as 40+ tools (`get_campaigns`, `get_insights`, `update_adset`, `pause`,
  etc.) e disponibiliza pro Caio raciocinar e agir.
- Referência de formato em `mcp-meta-ads.example.json` (com env vars, sem tokens reais).

## Passo 4 — Alma + Conhecimento

- **SOUL / system prompt:** cole o conteúdo de `SOUL.md` deste diretório.
- **Knowledge (nativo):** aponte a base de conhecimento do Hermes para
  `packages/caio-trafego/agent/knowledge/` (5 arquivos: `marketing-skills.md`, `playbook.md`,
  `benchmarks.md`, `raiz_vital.md`, `sinapse_ref/paid-traffic.md`). São a referência que o Caio
  consulta pra raciocinar.

## Passo 5 — Smoke test (Telegram)

1. `"Caio, lê a conta e me dá o status das campanhas"` → deve chamar tools MCP e responder com dados.
2. `"Caio, gera o relatório de hoje"` → resumo executivo.
3. **Missão real #1:** `"Caio, por que parou de entrar cliente desde quinta? Audita a conta."`

## Passo 6 — Operação completa (cron nativo do Hermes)

Os 3 ciclos diários viram 3 cron jobs nativos, entregando o resultado no Telegram do grupo:

```bash
# 08:00 — análise matinal
hermes cron create \
  --prompt "Ciclo matinal: puxe tudo ativo na conta Meta, classifique BOM/ALERTA/CRITICO/PAUSAR, execute acoes autonomas dentro dos guardrails e liste candidatos a aprovacao." \
  --schedule "0 8 * * *" --timezone America/Sao_Paulo --deliver telegram

# 14:00 — check da tarde
hermes cron create \
  --prompt "Check da tarde: ritmo de budget (risco de estourar antes das 16h), ajustes finos de bid (+-20%) e cheque aprovacoes pendentes." \
  --schedule "0 14 * * *" --timezone America/Sao_Paulo --deliver telegram

# 20:30 — relatório diário
hermes cron create \
  --prompt "Relatorio diario no grupo: resumo executivo do dia + recomendacoes pro dia seguinte." \
  --schedule "30 20 * * *" --timezone America/Sao_Paulo --deliver telegram

hermes cron list   # confirma os 3 jobs
```

- **Travas de segurança que ficam ON nos primeiros dias** (recomendação):
  - Ações *mutating* (pausar/ajustar/duplicar) só após **OK do Kaue** no grupo.
  - Caio **diagnostica antes de agir** na primeira rodada.
- Roda enquanto seu PC estiver ligado. 24/7 = fase VPS (depois) — aí migra esses mesmos
  comandos pro Hermes na VPS.
- Memória: o Hermes tem **memória + learning loop nativos** entre sessões — começamos com a dele
  no MVP (decisão da sessão 2026-06-30).

---

## Backlog pós-MVP (registrado, não bloqueia)
- Memória persistente de decisões/hand-offs (Obsidian vs Graphify vs outro) — decidir.
- Deep research: melhor modelo p/ tool-use de tráfego × custo (DeepSeek v4 e concorrentes) + VPS barata 4GB.
- Minerar guia do Hermes/Okamoto (YouTube) pra refinar agentes.
- Promover mais workflows a skills ativas conforme ganhar confiança.
