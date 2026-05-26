
# Codex QA Prompt — Caio: Gestor de Tráfego Raiz Vital

## Missão

Você é um engenheiro de QA especialista em Python. Sua tarefa é auditar, testar, corrigir e deixar funcionalmente correto o agente **Caio — Gestor de Tráfego Meta Ads** localizado em `packages/caio-trafego/`. O agente está arquiteturalmente completo mas nunca foi executado com código real — só com mocks. Seu objetivo: garantir que `make test` passe 100% e que, ao conectar credenciais reais, o agente funcione sem erros.

---

## Contexto do Projeto

### O que é o Caio

Agente Python autônomo de gestão de Meta Ads para a Raiz Vital (cliente real). Roda 24/7 em VPS, gerencia campanhas Meta Ads, envia relatórios via WhatsApp às 20:30, solicita aprovações ao cliente via chat. Stack: Agno Framework + facebook-business SDK + Evolution API + APScheduler.

### Arquivos (todos em `packages/caio-trafego/`)

```
agent/
  caio.py              — Factory do agente Agno + system prompt + knowledge loader
  main.py              — Entry point + registro de ciclos no scheduler
  llm_router.py        — LLM routing: Groq (rotina) vs Claude (decisões complexas)
  tools/
    meta_ads.py        — Wrapper Meta Marketing API (facebook-business SDK) ~850 linhas
    whatsapp.py        — Evolution API (envio + polling de aprovação)
    scheduler.py       — APScheduler (cron 08:00/14:00/20:30 BRT)
  workflows/
    analyze.py         — Classificação de ad sets (CHAMPION/GOOD/ALERT/CRITICAL/INSUFFICIENT/FATIGUED)
    optimize.py        — Ações autônomas (pause, bid, duplicate)
    approve.py         — Fluxo WhatsApp + timeout 2h
    report.py          — Relatório diário TXT
  knowledge/
    benchmarks.md      — CPL/CTR/ROAS benchmarks Brasil
    raiz_vital.md      — Contexto do cliente
    playbook.md        — Regras de otimização + InsightfulPipe skills
    sinapse_ref/
      paid-traffic.md  — Meta Ads técnico (CBO/ABO, segmentação, algoritmo)
harnesses/
  test_analyze.py      — 3 cenários com mocks
  test_report.py       — Valida formato do relatório
  test_approve.py      — 3 cenários de aprovação (OK/NÃO/timeout)
  mocks/               — JSONs com dados de campanhas simuladas
config/
  settings.yaml        — Thresholds, schedule, guardrails
  .env.example         — Template de variáveis (NUNCA commitar .env real)
requirements.txt
Makefile
```

---

## Spec — Acceptance Criteria (Story-017)

```gherkin
DADO que o settings.yaml está configurado com thresholds e credenciais
QUANDO o ciclo de análise das 08:00 é executado
ENTÃO o agente classifica cada ad set como BOM/ALERTA/CRÍTICO/PAUSAR
  E toma ações autônomas dentro dos guardrails

DADO um ad set com CPL > R$35 por 2 dias consecutivos
QUANDO o agente analisa os dados (mínimo 50 cliques)
ENTÃO pausa o ad set automaticamente
  E registra a ação no log com timestamp e motivo

DADO uma ação que requer aprovação (ex: novo criativo)
QUANDO o agente identifica a necessidade
ENTÃO envia mensagem estruturada no grupo WhatsApp
  E aguarda resposta por até 2 horas
  E bloqueia + registra se não houver resposta

DADO que são 20:30 BRT
QUANDO o cron job do relatório é acionado
ENTÃO gera TXT com RESUMO EXECUTIVO (5 métricas) e RELATÓRIO COMPLETO
  E envia para o grupo WhatsApp

DADO campanhas com menos de 50 cliques
QUANDO o agente analisa os dados
ENTÃO NÃO toma nenhuma ação de otimização
  E flag "dados insuficientes" é registrada

DADO que os harnesses estão configurados com mocks
QUANDO executo `make test`
ENTÃO todos os cenários passam sem erro
```

---

## Checklist de Auditoria — Execute Nesta Ordem

### FASE 1 — Verificação de Imports e Dependências

**1.1 Verificar imports do `meta_ads.py`**

Confirme que estes imports existem na facebook-business SDK (versão >= 19.0.0):
- `from facebook_business.adobjects.adcreative import AdCreative` — verifique se este é o path correto
- `from facebook_business.adobjects.campaign import Campaign` — verifique se existe
- `from facebook_business.adobjects.adaccount import AdAccount` — já existia
- `from facebook_business.adobjects.adset import AdSet` — já existia
- `from facebook_business.adobjects.ad import Ad` — já existia

Se algum path estiver errado, corrija para o path correto do SDK.

**1.2 Verificar consistência de nomes de método**

Em `meta_ads.py`, o método helper foi renomeado de `_get_adset_insights` para `_fetch_adset_insights_raw`. Verifique se TODAS as referências internas ao método antigo foram atualizadas. Busque por `_get_adset_insights` no arquivo — se existir, substitua por `_fetch_adset_insights_raw`.

**1.3 Verificar `whatsapp.py` — método `send_critical_alert`**

Em `caio.py`, o tool `whatsapp_tool.send_critical_alert` é injetado no agente. Verifique se o método `send_critical_alert` existe na classe `WhatsAppTool` em `tools/whatsapp.py`. Se não existir, adicione-o com esta assinatura:
```python
def send_critical_alert(
    self,
    problem: str,
    campaign: str,
    data: str,
    action_taken: str,
    next_step: str,
    group_id: str | None = None,
) -> dict:
    """Envia alerta crítico formatado para o grupo WhatsApp."""
    text = (
        "🚨 Caio — ALERTA CRÍTICO\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"PROBLEMA: {problem}\n"
        f"CAMPANHA: {campaign}\n"
        f"DADO: {data}\n"
        f"AÇÃO TOMADA: {action_taken}\n"
        f"PRÓXIMO PASSO: {next_step}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return self.send_message(text, group_id)
```

**1.4 Verificar `llm_router.py` — singleton no módulo**

O arquivo define `router = LLMRouter()` no nível do módulo. Isso executa `_check_groq()` no import, o que é seguro (só lê env var). Mas o `__init__` usa `logger.warning` — verifique se o logger está definido antes do singleton. Se não, mova a linha `router = LLMRouter()` para depois de todos os métodos da classe mas antes do fim do arquivo, garantindo que o módulo de logging já esteja configurado.

**1.5 Verificar `caio.py` — import do LLMRouter**

Confirme que `from .llm_router import LLMRouter, router` (ou similar) está no arquivo e que não gera ImportError circular.

**1.6 Verificar `requirements.txt`**

Confirme que `groq>=0.9.0` está listado. O nome correto do pacote PyPI é `groq` (da Groq Inc.). Confirme que não há typo.

---

### FASE 2 — Análise de Lógica nos Workflows

**2.1 `workflows/analyze.py` — Classificação**

Leia o arquivo completo e verifique:
- O enum `AdSetState` tem todos os estados: CHAMPION, GOOD, ALERT, CRITICAL, INSUFFICIENT, FATIGUED
- A função `_classify()` cobre todos os casos de threshold do `settings.yaml`
- A flag `days_above_cpl_threshold` é usada corretamente para a regra "2 dias consecutivos"
- Campanhas com `clicks < 50` retornam `AdSetState.INSUFFICIENT` sem nenhuma ação
- O estado `FATIGUED` é acionado quando `frequency > 3.5`

Se alguma lógica estiver incorreta ou incompleta, corrija com base nos thresholds do `settings.yaml`:
```yaml
cpl_max: 35.00
cpl_alert: 25.00
cpl_critical: 105.00
ctr_min: 1.5
ctr_pause: 1.0
roas_min: 2.0
frequency_pause: 3.5
min_clicks_to_act: 50
```

**2.2 `workflows/optimize.py` — Ações Autônomas**

Verifique:
- Ações para cada estado de ad set (CRITICAL → pause, ALERT → adjust_bid, CHAMPION → candidate para duplicação)
- O método `optimize_wf.run()` retorna um objeto com atributo `approvals_sent` (usado em `main.py`)
- O log de ações é escrito em `logs/actions-YYYY-MM-DD.log` (o diretório `logs/` tem `.gitkeep`)

**2.3 `workflows/report.py` — Relatório**

Verifique:
- O relatório tem EXATAMENTE duas seções: "⚡ RESUMO EXECUTIVO" e "📋 RELATÓRIO COMPLETO"
- A seção de resumo tem 5 métricas: spend total, leads total, CPL médio, ad sets ativos, ações tomadas
- Mensagens longas são split em chunks de 4000 chars para WhatsApp
- O relatório é salvo em `logs/report-YYYY-MM-DD.txt`

**2.4 `workflows/approve.py` — Timeout e Polling**

Verifique:
- O método `poll_approval_response()` em `whatsapp.py` é chamado com `timeout_hours=2`
- O resultado `ApprovalDecision.TIMEOUT` bloqueia a ação e registra no log
- A resposta "OK" (case-insensitive) aprova; "NÃO", "NAO", "NO", "N" rejeitam

**2.5 `agent/main.py` — Scheduler**

Verifique:
- `morning_cycle()` chama `analyze_wf.run(days=7)` (análise semanal)
- `afternoon_cycle()` chama `analyze_wf.run(days=1)` (check diário)
- `daily_report_cycle()` chama `report_wf.run(analysis, optimize_result, approvals_pending[:])`
- `approvals_pending.clear()` acontece APÓS o relatório, não antes

---

### FASE 3 — Auditoria dos Harnesses

**3.1 Execute (dry-run mental) cada harness**

Leia `harnesses/test_analyze.py`, `harnesses/test_report.py` e `harnesses/test_approve.py`.

Para cada harness, verifique:
- Os imports estão corretos (paths relativos vs absolutos)
- Os mocks em `harnesses/mocks/*.json` têm todos os campos que os testes esperam
- As assertions são válidas (não hardcode valores que podem mudar com a lógica)

**3.2 Corrigir harnesses quebrados**

Se qualquer harness importar de um path que não existe, corrija o import. Se usar um campo de `AdSetMetrics` que não existe no dataclass, corrija.

**3.3 Verificar que `make test` funcionaria**

Leia o `Makefile`. Os 3 comandos são:
```
python harnesses/test_analyze.py
python harnesses/test_report.py  
python harnesses/test_approve.py
```

Os harnesses são executados como scripts standalone (não como pytest). Cada um deve ter um bloco `if __name__ == "__main__":` e deve terminar com print de sucesso ou raise de erro.

---

### FASE 4 — Meta Ads API Compatibility

**4.1 Verificar métodos de instância vs classe no SDK**

Para cada método de ação (`pause_ad`, `pause_ad_set`, etc.), verifique se a forma de update está correta. O SDK facebook-business usa:
```python
# CORRETO para update de status:
ad = Ad(ad_id)
ad[Ad.Field.status] = Ad.Status.paused
ad.remote_update()
# OU
ad.api_update(params={"status": "PAUSED"})
```

Verifique qual forma o código atual usa e se está consistente com a versão `facebook-business>=19.0.0`.

**4.2 Verificar `export_all_data()`**

Em vários novos métodos de leitura, o código chama `.export_all_data()` nos objetos SDK. Verifique se este método existe nos objetos `Campaign`, `AdSet`, `Ad`, `AdCreative` da versão 19.x. Se não existir, use `.get_all_data()` ou converta para dict manualmente com `dict(obj)`.

**4.3 Verificar `get_ad_images()` e `get_ad_videos()`**

Confirme que `AdAccount` tem os métodos `get_ad_images()` e `get_ad_videos()`. Se não tiver (API mudou), comente os métodos com um `# TODO: verificar disponibilidade na API` e retorne lista vazia.

---

### FASE 5 — Melhorias de Robustez

**5.1 Adicionar retry em operações críticas**

Os métodos de ação em `meta_ads.py` (`pause_ad`, `pause_ad_set`, `adjust_bid`) não têm retry. Adicione retry simples com tenacity (já está nos requirements):

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def pause_ad_set(self, adset_id: str, reason: str = "") -> dict[str, Any]:
    # ... código existente
```

Aplique em: `pause_ad`, `pause_ad_set`, `resume_ad`, `resume_ad_set`, `adjust_bid`.

**5.2 Garantir que `logs/` existe**

Em `workflows/optimize.py` e `workflows/report.py`, antes de escrever em `logs/`, adicionar:
```python
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
```

**5.3 Verificar `_days_to_preset()` para valores não mapeados**

O método atual:
```python
presets = {1: "yesterday", 7: "last_7d", 14: "last_14d", 30: "last_30d"}
return presets.get(days, f"last_{days}d")
```

O fallback `f"last_{days}d"` pode não ser válido para todos os valores. A Meta API aceita: `today`, `yesterday`, `last_3d`, `last_7d`, `last_14d`, `last_28d`, `last_30d`, `last_90d`. Para valores não suportados, use `"last_7d"` como fallback seguro.

**5.4 Verificar `.env.example` tem `GROQ_API_KEY`**

Leia `config/.env.example`. Se não tiver `GROQ_API_KEY=`, adicione:
```
# LLM Routing (opcional — sem esta chave, todas as tarefas usam Claude)
GROQ_API_KEY=
```

---

### FASE 6 — Verificação Final

**6.1 Lint check mental**

Verifique nos arquivos Python:
- Sem f-strings com `\n` (Python < 3.12 não permite)
- Sem `from __future__ import annotations` faltando em arquivos que usam `X | Y` type hints
- Sem imports circulares entre `caio.py`, `llm_router.py` e os workflows

**6.2 Settings.yaml completo**

Leia `config/settings.yaml`. Verifique se tem as chaves que os workflows esperam:
- `thresholds.cpl_max`
- `thresholds.cpl_alert`
- `thresholds.cpl_critical`
- `thresholds.ctr_min`
- `thresholds.ctr_pause`
- `thresholds.frequency_pause`
- `thresholds.min_clicks_to_act`
- `budget.max_daily_per_adset`
- `schedule` (horários dos ciclos)
- `champion` (critérios de campeão)
- `agent.llm_model` (model ID padrão)

Se alguma chave estiver faltando mas for referenciada no código, adicione ao yaml com valor padrão sensato.

**6.3 Verificar `caio.py` — `_load_knowledge()` com `rglob`**

O método foi atualizado para usar `rglob("*.md")` ao invés de `glob("*.md")`. Verifique que o `relative_to()` está sendo chamado corretamente e que o path do arquivo é legível. Se `rglob` não estiver implementado, aplique:
```python
def _load_knowledge() -> str:
    parts = []
    for md_file in sorted(_KNOWLEDGE_DIR.rglob("*.md")):
        rel = md_file.relative_to(_KNOWLEDGE_DIR)
        content = md_file.read_text(encoding="utf-8")
        parts.append(f"## {rel}\n\n{content}")
    return "\n\n---\n\n".join(parts)
```

---

## Como Executar os Testes

```bash
cd packages/caio-trafego

# Instalar dependências
pip install -r requirements.txt

# Executar todos os harnesses
make test

# Verificar lint
make lint

# Verificar se há erros de import
python -c "from agent.tools.meta_ads import MetaAdsTool; print('meta_ads OK')"
python -c "from agent.tools.whatsapp import WhatsAppTool; print('whatsapp OK')"
python -c "from agent.llm_router import LLMRouter; print('llm_router OK')"
python -c "from agent.caio import build_caio; print('caio OK')"
python -c "from agent.workflows.analyze import AnalyzeWorkflow; print('analyze OK')"
python -c "from agent.workflows.report import ReportWorkflow; print('report OK')"
```

---

## Resultado Esperado

Após sua auditoria e correções:

1. `make test` executa sem erros — todos os 3 harnesses passam
2. `make lint` sem erros críticos (ruff)
3. Todos os imports Python funcionam sem `ImportError`
4. Toda lógica de threshold está correta e testada
5. Retry em ações críticas de Meta API
6. `logs/` directory é criado automaticamente
7. `.env.example` tem todos os campos necessários incluindo `GROQ_API_KEY`

**O que NÃO fazer:**
- Não conectar APIs reais (sem credenciais disponíveis)
- Não alterar a arquitetura ou estrutura de arquivos
- Não remover métodos existentes — só adicionar ou corrigir
- Não commitar `.env` com valores reais

**Quando estiver tudo correto:** reportar lista de bugs encontrados + fixes aplicados + status final de cada harness.

---

*Story-017 InProgress | Raiz Vital × Zvision | Sprint 1 — 600 potes em 14 dias*
