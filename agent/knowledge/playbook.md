# Playbook de Otimização — Caio

## Regras Absolutas (NUNCA violar)

1. NUNCA gastar além do budget diário configurado sem aprovação explícita do Kaue
2. NUNCA pausar todas as campanhas ao mesmo tempo sem alerta e justificativa
3. NUNCA fazer upload de criativo sem aprovação — independente do motivo
4. NUNCA tomar ação em ad set/anúncio com menos de 50 cliques (dados insuficientes)
5. NUNCA ignorar um erro de API — registrar, alertar e aguardar resolução
6. SEMPRE registrar toda ação no log com timestamp, motivo e dado
7. SEMPRE notificar o grupo quando recalibrar thresholds (valores anteriores e novos)

## Ordem de Prioridade nas Otimizações

1. **Pare o sangramento** — pausar o que está gastando sem retorno (CPL crítico)
2. **Escale o que funciona** — duplicar ad sets campeões dentro do budget aprovado
3. **Ajuste fino** — bid adjustments na zona de atenção
4. **Reporte e recomende** — sempre com dados, nunca com opinião sem número

## Regras de Decisão por Situação

### Dias 1–3: Campanha Nova (dados insuficientes)
- NÃO pausar nada com menos de 50 cliques
- NÃO ajustar bid antes de 48h de dados
- Monitorar CPM e alcance — se CPM > 2x benchmark, algo está errado na segmentação
- Reportar no daily com flag "dados insuficientes para otimização"
- Verificar aprovação de anúncios pela Meta (policy compliance)

### Dias 3–7: CPL Subindo Progressivamente
- CPL entre R$25–35: ajustar bid -10% e monitorar 24h
- CPL acima de R$35 por 2 dias consecutivos: pausar ad set + solicitar revisão de criativo ao Kaue
- CPL explodindo de um dia para o outro: alerta crítico (possível mudança de algoritmo ou leilão)

### Ad Set Campeão (CPL < R$20, ROAS > 3x)
- Dia 3: documentar como "ad set campeão" no log
- Dia 5: propor duplicação ao Kaue se budget permite
- Dia 7: se ainda performando, duplicar autonomamente SE budget total cabe (guardrail obrigatório)

### Criativo Fatigado (Frequência > 3.5)
- Pausar o anúncio específico (NÃO o ad set inteiro)
- Solicitar novo criativo ao Kaue com dados de frequência e queda de CTR
- Se o ad set tem outros criativos rodando, deixar continuar

### Budget Consumido Antes das 16h
- Alerta imediato no grupo
- NÃO aumentar budget autonomamente
- Analisar distribuição do gasto (possível leilão competitivo de manhã)
- Registrar no log para calibrar programação de delivery

## Ajuste de Bid — Regras

| Situação | Ajuste |
|----------|--------|
| CPL entre R$25–35 (zona de atenção) | -10% |
| ROAS entre 1.8–2.0x (abaixo do mínimo mas recuperável) | -10% |
| CPL < R$15 por 3+ dias, ROAS > 4x | +10% (para escalar volume) |
| Limite máximo de qualquer ajuste | ±20% do bid atual |

## Duplicação de Ad Set — Checklist Obrigatório

Antes de duplicar (mesmo com autonomia):
- [ ] CPL < R$20 por ≥ 3 dias consecutivos
- [ ] CTR > 3% com volume mínimo de 500 cliques
- [ ] ROAS > 3.0x sustentado
- [ ] Budget do ad set duplicado cabe dentro do budget diário total aprovado
- [ ] Ad set não está em período de revisão da Meta

Se QUALQUER item acima não for atendido → solicitar aprovação do Kaue.

## Padrões de Copy que Funcionam em Saúde (referência para solicitações)

- **Abertura:** problema específico do público ("Acorda às 3h com calor intenso?")
- **Validação:** científica sem claim médico ("Desenvolvido com extratos naturais estudados")
- **Prova social:** depoimentos sem antes/depois explícito
- **CTA:** direto para WhatsApp ("Fale com nossa especialista agora")
- **EVITAR:** "cura", "elimina completamente", "garantido", claims comparativos com medicamentos

## Recalibração de Thresholds (Dia 7)

Critérios para recalibrar:
- Mínimo 7 dias de operação
- Mínimo 500 cliques coletados
- Dados de pelo menos 2 ad sets ativos

Processo:
1. Calcular CPL médio real dos últimos 7 dias
2. Calcular CTR médio real
3. Calcular ROAS médio real
4. Novo threshold = percentil 75 dos dados coletados (conservador)
5. Notificar grupo com valores anteriores vs novos
6. Atualizar settings.yaml com os novos valores

## Ciclos de Operação Detalhados

### 08:00 — Análise Matinal
1. Fetch completo de todos os ad sets e anúncios ativos
2. Calcular métricas do dia anterior (fechado)
3. Classificar cada ad set: BOM / ALERTA / CRÍTICO / PAUSAR
4. Executar ações autônomas (pausas, ajustes de bid)
5. Identificar candidatos a aprovação (duplicação, criativo novo)
6. Log completo de todas as ações

### 14:00 — Check da Tarde
1. Verificar performance da manhã
2. Checar se budget está no ritmo certo (risco de consumo antes das 16h)
3. Ajustes finos se necessário
4. Verificar aprovações pendentes (se houver resposta do Kaue)

### 20:30 — Relatório Diário
1. Consolidar dados do dia
2. Gerar relatório TXT (resumo executivo + completo)
3. Enviar para o grupo WhatsApp Raiz Vital
4. Registrar recomendações para o dia seguinte

### Tempo Real — Alertas Críticos
- CPL > R$105 (3x threshold)
- Budget consumido antes das 16h
- Anúncio reprovado pela Meta
- Queda > 50% na conversão
- Erro de API que impede operação

---

## Auditoria de Conta — Checklist Matinal

### Saúde Estrutural
- [ ] Todas as campanhas em modo correto (objetivo = Mensagens ou Lead Gen)
- [ ] Nenhum ad set com status "Em análise" por mais de 24h → alerta imediato
- [ ] Budget total ≠ 0 em nenhum ad set ativo
- [ ] Nenhum anúncio reprovado sem notificação ao Kaue

### Saúde de Performance
- [ ] CPL de cada ad set classificado (BOM/ALERTA/CRÍTICO/INSUFICIENTE)
- [ ] Frequência verificada em todos os ad sets ativos
- [ ] Ad sets com < 50 cliques = flag "dados insuficientes"
- [ ] Budget consumido antes das 12h = alerta automático

### Oportunidades
- [ ] Algum ad set com CPL < R$20 por 3+ dias? → candidato a duplicação
- [ ] Algum ad set no percentil 75 superior de CTR? → candidato a aumento de bid
- [ ] Algum criativo com frequência > 3.5? → pausar anúncio, solicitar novo

---

## Alocação de Budget — Marginal CPA Analysis

Budget deve fluir para onde o ROAS marginal é mais alto.
Não basta ter CPL < threshold — compare ENTRE ad sets.

### Algoritmo de Redistribuição (quando budget total fixo)

1. Ranquear ad sets por CPL (menor = melhor)
2. Calcular "score de eficiência": CTR × (1/CPL) × (1/frequency)
3. Ad sets no quartil superior (score mais alto) = candidatos a +20% budget
4. Ad sets no quartil inferior (score mais baixo) = candidatos a -20% budget
5. NUNCA redistribuir sem aprovação se mudança > 30% do budget atual do ad set

### Tabela de Decisão Budget

| Situação | Ação |
|----------|------|
| CPL < R$20, CTR > 3%, freq < 2.0 | +20% budget (autônomo, dentro do total) |
| CPL R$20-25, CTR > 2%, freq < 3.0 | Manter. Monitorar 24h |
| CPL R$25-35 | -10% bid. Monitorar 24h |
| CPL > R$35 por 2 dias | Pausar. Notificar Kaue |

### Regra de Diversificação
Manter SEMPRE pelo menos 2 ad sets ativos por produto.
Se New Woman tiver 1 único ad set → prioridade máxima para diversificar.

---

## Ranqueamento de Criativos

### Score de Criativo (calcular semanalmente)

Score = (CTR × 0.4) + (Hook Rate × 0.3) + (ROAS × 0.2) + (1/frequency × 0.1)

- CTR: taxa de clique no link (%)
- Hook Rate: % que assistiu 3s+ do vídeo
- ROAS: receita / gasto (estimado via leads × R$150)
- Frequency: inverso normalizado

### Classificação de Criativos

| Tier | Score | Status | Ação |
|------|-------|--------|------|
| S-Tier | Top 10% | Campeão | Proteger. Duplicar o ad set. |
| A-Tier | Top 25% | Bom | Manter. Monitorar frequência. |
| B-Tier | Top 50% | Aceitável | Substituir se freq > 3.0 |
| C-Tier | Bottom 50% | Fraco | Pausar após 500 impressões + CPL > threshold |

### Quando Solicitar Novo Criativo ao Kaue

- 1 ou mais criativos C-Tier com frequência > 2.5
- Todos os criativos de um ad set com CTR caindo por 2 dias consecutivos
- Criativo campeão com frequência > 3.5 (fadiga iminente)
- Anúncio reprovado pela Meta por claim de saúde

---

## Roadmap de Escala — Sprint 1 (14 dias)

### Fase 1: Dados (Dias 1-3)
- Objetivo: Coletar dados suficientes para decisão
- Ação: Monitorar apenas. NENHUMA otimização.
- Critério de saída: ≥ 2 ad sets com ≥ 50 cliques cada

### Fase 2: Otimização (Dias 4-7)
- Objetivo: Encontrar o ad set campeão
- Ação: Pausar o que não funciona. Ajustar bids.
- Critério de saída: ≥ 1 ad set com CPL < R$20 por 3 dias consecutivos

### Fase 3: Escala (Dias 7-14)
- Objetivo: Multiplicar o que funciona
- Ação: Duplicar ad set campeão (com aprovação ou autonomamente se budget cabe)
- Critério de saída: 600 potes vendidos OU budget esgotado

### Sinais de Escala Prematura (EVITAR)
- Escalar antes de 3 dias de CPL estável
- Escalar sem pelo menos 50 leads no histórico
- Dobrar budget de uma vez (aumentar 50% máximo por semana)
- Escalar durante learning phase da Meta

### Meta por Dia (referência)
Para 600 potes em 14 dias:
- Meta diária: 43 potes/dia
- Conversão WhatsApp → venda: 20-35%
- Leads necessários/dia: 120-215 leads
- CPL meta: R$5-10/lead (budget total estimado: R$15-25k)
