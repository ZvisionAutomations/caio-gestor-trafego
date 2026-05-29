# Caio — Gestor de Tráfego Raiz Vital

Agente autônomo de gestão de Meta Ads 24/7 para a Raiz Vital.
Opera campanhas, otimiza dentro de guardrails, solicita aprovações via WhatsApp
e envia relatório diário às 20:30.

**Objetivo Sprint 1:** Vender 600 potes (R$90k) em 14 dias.

---

## Estrutura

```
packages/caio-trafego/
├── agent/
│   ├── caio.py              # Agente principal Agno + system prompt
│   ├── main.py              # Entry point + scheduler
│   ├── tools/
│   │   ├── meta_ads.py      # Meta Marketing API (facebook-business SDK)
│   │   ├── whatsapp.py      # Evolution API — mensagens + polling
│   │   └── scheduler.py     # APScheduler — cron 08:00/14:00/20:30 BRT
│   ├── workflows/
│   │   ├── analyze.py       # Classificação de ad sets
│   │   ├── optimize.py      # Ações autônomas
│   │   ├── approve.py       # Fluxo de aprovação WhatsApp
│   │   └── report.py        # Relatório diário TXT
│   └── knowledge/
│       ├── benchmarks.md    # Benchmarks saúde/suplementos BR
│       ├── raiz_vital.md    # Contexto do cliente
│       └── playbook.md      # Regras de otimização
├── config/
│   ├── settings.yaml        # Thresholds, schedule, guardrails
│   └── .env.example         # Template de variáveis de ambiente
├── harnesses/               # Testes com mocks (sem API real)
└── logs/                    # Logs de ações e relatórios
```

---

## Setup

```bash
cd packages/caio-trafego

# 1. Dependências
make install

# 2. Configuração
cp config/.env.example config/.env
# Preencher .env com credenciais reais

# 3. Testar com mocks (sem credenciais necessárias)
make test

# Windows sem GNU Make instalado
python scripts/run_harnesses.py

# 4. Go-live (após preencher .env)
make run
```

---

## Checklist de Go-Live

### Pré-go-live (sem Fernando)
- [ ] `make test` passando com todos os harnesses
- [ ] `config/settings.yaml` revisado (thresholds, schedule)
- [ ] Evolution API conectada ao grupo WhatsApp Raiz Vital
- [ ] Cron jobs testados na VPS
- [ ] Log de ações funcionando (`logs/`)

### Com Fernando (2ª reunião — BLOQUEANTE)
- [ ] `META_ACCOUNT_ID` preenchido no `.env`
- [ ] `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN` preenchidos
- [ ] `budget.max_daily_per_adset` definido em `settings.yaml`
- [ ] `WHATSAPP_GROUP_ID` configurado

### Sequência de Go-Live
1. **Modo read-only por 24h** — agente analisa mas não executa ações
2. **Validar relatório do Dia 1 com o Kaue**
3. **Liberar ações autônomas** (pausas + ajustes de bid)
4. **Liberar ciclo completo** de autonomia graduada

---

## Autonomia Graduada

| Ação | Requer Aprovação? |
|------|-------------------|
| Pausar anúncio/ad set (CPL crítico) | Não |
| Reativar anúncio pausado | **SIM — Kaue** |
| Ajustar bid ±20% | Não |
| Duplicar ad set (budget disponível) | Não |
| Subir criativo novo | **SIM — Kaue** |
| Criar campanha/ad set do zero | **SIM — Kaue** |
| Aumentar budget além do limite | **SIM — Kaue** |
| Duplicar ad set (budget excedido) | **SIM — Kaue** |

**Timeout de aprovação:** 2 horas. Sem resposta = ação bloqueada + log.

---

## Thresholds Padrão (recalibrar aos 7 dias)

| Métrica | Threshold | Ação |
|---------|-----------|------|
| CPL | > R$35 | Pausa automática |
| CPL | R$25–35 | Ajuste de bid -10% |
| CPL | > R$105 | Alerta crítico imediato |
| CTR | < 1% após 1.000 impressões | Pausa |
| Frequência | > 3.5 | Pausar criativo + solicitar novo |
| ROAS | < 2.0x | Monitorar |
| Cliques mínimos | < 50 | Não agir (dados insuficientes) |

---

## Referências

- **ADR:** `ADR-caio-gestor-trafego.md`
- **SPEC:** `SPEC-caio-gestor-trafego.md`
- **Story:** `docs/stories/story-017-caio-gestor-trafego.md`
- **Meta SDK:** [facebook-business](https://github.com/facebook/facebook-python-business-sdk)
- **Agno:** https://docs.agno.com
