# Config v2 — MoA + Fallback + Auxiliary (story-085)

> Alvo pra evoluir o MVP (GLM Flash único) → v2. **Aplicar via CLI**, não hand-edit cru:
> a v0.17 do Hermes diverge da doc pública (lição do MVP), então o schema exato de cada bloco
> deve ser confirmado com `--help` na própria VPS antes de aplicar. Sempre reiniciar o gateway após.

## Modelo principal (mantém — já validado)
```
model.default = z-ai/glm-4.7-flash   # Modo Operação (Executor + Conversa)
```

## Modo Estrategista (MoA) — ensemble só em tarefa difícil
Config-alvo (`config.yaml` → `moa:` — ref. GitHub issue #38952):
```yaml
moa:
  profiles:
    estrategista:
      reference_models:
        - z-ai/glm-4.7            # mesmo family do executor, raciocínio líder
        - deepseek/deepseek-v3.2  # thinking+tool (plano B se instável)
        - qwen/qwen3.5-35b-a3b    # diversidade de raciocínio
      aggregator_model: z-ai/glm-4.7
      reasoning_effort: high
      min_successful_references: 2
```
Aplicar/validar:
```bash
hermes moa --help          # confirmar subcomando de configure na v0.17
hermes moa configure       # se existir; senão editar config.yaml + reiniciar gateway
# sessão: /moa on  → agente chama MoA em sub-tarefas difíceis; /moa status confere
```
⚠️ **TESTE AO VIVO obrigatório** (benchmark ≠ comportamento): validar que cada reference model
faz tool-call limpo no Hermes real. DeepSeek quebrou no MVP → se quebrar, remover do ensemble.

## Fallback — resiliência (lição: DeepSeek caiu no MVP)
```bash
hermes fallback --help     # confirmar schema (config comentado da v0.17 usa `fallback_model:`;
                           # doc pública usa `fallback_providers:` — CONFIRMAR na versão)
hermes fallback add ...    # chain: gemini-flash-latest → llama-3.3-70b-instruct
```

## Auxiliary — offload barato (estica os $5)
Config-alvo (`config.yaml` → `auxiliary:` — ref. tutorial OpenRouter):
```yaml
auxiliary:
  title:       { provider: openrouter, model: google/gemini-flash-latest }
  compression: { provider: openrouter, model: google/gemini-flash-latest }
```

## Relatórios por pessoa (crons)
Após capturar os chat_ids (cada pessoa manda 1 msg pro bot → `channel_directory.json`):
```bash
# por pessoa, os 3 ciclos (exemplo p/ 1 chat_id):
hermes cron create --name "caio-08h-<nome>" --deliver telegram:<chat_id> "0 11 * * *" "<prompt matinal>"
hermes cron create --name "caio-14h-<nome>" --deliver telegram:<chat_id> "0 17 * * *" "<prompt tarde>"
hermes cron create --name "caio-2030-<nome>" --deliver telegram:<chat_id> "30 23 * * *" "<prompt relatorio>"
```
Chat_id conhecido hoje: `8398330656` (Zvision/operador). Faltam Fernando e Kaue.

## Ordem de aplicação (gotcha do MVP)
1. Parar gateway (`sudo systemctl stop hermes-gateway` / esperar uvx encerrar).
2. Editar config.yaml (SOUL-v2.md → `~/.hermes/SOUL.md`; moa/auxiliary; fallback via CLI).
3. Reiniciar gateway limpo → esperar ~10s uvx subir → `/new` numa conversa nova.
4. Smoke: tarefa difícil (plano de destravamento) deve acionar MoA; tarefa trivial não.
5. Validar REGRA ZERO em todos os modos + unidades (centavos ÷100).
