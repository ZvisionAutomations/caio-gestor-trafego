# meta-ads-mcp-guarded

Proxy MCP que envolve o `meta-ads-mcp` real com **guardrails determinísticos** antes de repassar tool calls mutantes à Graph API da Meta. É o **artefato A** do Caio v2 (runtime Hermes) — ver `packages/caio-trafego/docs/hermes-v2-slicing.md`.

## Por que existe
O Hermes é um LLM (GLM-4.7-flash) governado por prompt + tools de um MCP. LLM não é determinístico: pode alucinar um `adset_id` plausível-mas-inválido, estourar budget, ou violar compliance. Um guardrail que depende do LLM lembrar de se comportar **não é guardrail**. Este proxy intercepta as tools mutantes e aplica regras em código.

## Como funciona
- O Hermes aponta o MCP `meta-ads` para **este** server, no lugar do `meta-ads-mcp`.
- No boot, ele **spawna o `meta-ads-mcp` real como processo filho** (stdio) e faz **passthrough** de todas as tools.
- Tools **read-only** (`get_*`, `search_*`) passam direto.
- Tools **mutantes** (`create_ad`, `update_adset`, `update_campaign`, `create_adset`, `create_campaign`, `update_ad`, `create_ad_creative`, `upload_ad_image`) passam pela **pipeline de interceptors** antes de chegar ao filho.

Zero divergência de upstream: o `meta-ads-mcp` continua vindo via `npx` e atualizável.

## Pipeline de interceptors (ordem — hermes-v2-slicing §1.1)
| Ordem | Interceptor | Story | Status |
|---|---|---|---|
| 1 | Validação de schema (IDs `^\d+$`, campos obrigatórios, fail-safe) | 091 | ✅ |
| 2 | Guardian (circuit-breaker, teto R$, anti-flapping, decision log) | 088 | ✅ |
| 3 | Compliance (termos proibidos health/wellness, fail-closed) | 094 | ✅ |
| 4 | State machine (bloqueia mutação em adset em estado errado) | 089 | ✅ |

Cada story pluga sua função em `src/interceptors.js::buildPipeline()`.

**Módulos relacionados:** `guardian.js` (088), `compliance.js` (094), `state_machine.js`+`state_store.js`+`reconciler.js`+`reconcile-cron.js` (089), `rules.js` (090, avaliador determinístico), `config.js` (lê `guardrails.yaml`).

**Config:** `GUARDED_CONFIG_PATH` → `packages/caio-trafego/hermes/guardrails.yaml`.

**DB (089) — least-privilege (2 roles):**
| Env | Role | Quem usa |
|---|---|---|
| `CAIO_DATABASE_URL` | `caio_ro` (SELECT) | o **wrapper** (`index.js`) — só LÊ estado |
| `CAIO_DB_WRITE_URL` | `caio_rw` (SELECT/INSERT/UPDATE) | o **reconciler** (`reconcile-cron.js`) — ESCREVE estado |

Sem nenhuma das duas → state in-memory por ciclo (fallback dev, sem persistência). **Reconciler cron:** `node src/reconcile-cron.js` nos ciclos 08/14/20:30 (usa `CAIO_DB_WRITE_URL`, fallback `CAIO_DATABASE_URL`).

## Config no Hermes
```jsonc
{
  "mcpServers": {
    "meta-ads": {
      "command": "node",
      "args": ["/opt/caio/meta-ads-mcp-guarded/src/index.js"],
      "env": {
        "META_ACCESS_TOKEN": "${META_ACCESS_TOKEN}",
        "META_AD_ACCOUNT_ID": "${META_AD_ACCOUNT_ID}"
      }
    }
  }
}
```
O proxy repassa todo o env pro filho, então as mesmas credenciais valem.

### Env vars do proxy
| Var | Default | Uso |
|---|---|---|
| `GUARDED_CHILD_COMMAND` | `npx` | Comando do MCP filho |
| `GUARDED_CHILD_ARGS_JSON` | — | Array JSON exato de args (robusto a paths com espaço; tem precedência) |
| `GUARDED_CHILD_ARGS` | `-y meta-ads-mcp` | Args por espaço (conveniência) |

## Instalação
```bash
cd packages/meta-ads-mcp-guarded
npm install
```
> ⚠️ **Windows + Google Drive:** `npm install` falha com `EBADF` no filesystem virtual do Google Drive (`G:\Meu Drive`). Isso é do ambiente, não do código — instale/rode a partir de um disco NTFS local, ou (produção) direto na VPS Linux, onde não ocorre.

## Testes
```bash
npm test   # node --test
```
Cobre: validação de schema (unit), pipeline (unit, incl. fail-open) e integração end-to-end do proxy contra um MCP filho mockado (`test/mock-child.js`) — passthrough + bloqueio real, sem precisar de credencial Meta.
