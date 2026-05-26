# Meta Ads — Referência Técnica Raiz Vital

Destilado de sinapse-pesquisas/15-paid-traffic/research.md para o contexto do Caio.

## Arquitetura de Campanha

### CBO vs ABO — Decisão
- **CBO (Campaign Budget Optimization):** Recomendado quando há 3+ ad sets com histórico.
  Deixe o Meta alocar budget automaticamente. Melhor para escala.
- **ABO (Ad Set Budget Optimization):** Use em fase de teste (ad sets novos, sem histórico).
  Permite controle preciso por ad set. Budget diário individual por ad set.
- **Para o Sprint 1 da Raiz Vital:** ABO enquanto sem histórico suficiente. Migrar para CBO
  quando CPL estabilizar e houver 3+ ad sets com ≥ 500 cliques cada.

### Advantage+ Shopping (ASC)
- Só disponível para e-commerce com pixel histórico. **NÃO aplicável** à Raiz Vital neste sprint
  (vendas via WhatsApp, sem pixel de conversão histórico).
- Quando aplicável: deixar Meta otimizar criativos e audiências automaticamente.

### Estrutura Recomendada para WhatsApp Business
- 1 campanha por produto (New Woman / Alpha Pulse)
- 3-5 ad sets por campanha, cada um com segmentação diferente
- 3-5 anúncios por ad set (criativos diferentes para teste)
- Objetivo: Mensagens (WhatsApp) ou Lead Generation

## Segmentação — Audiências que Funcionam

### New Woman (Mulheres 45-60, climatério/menopausa)
Interesses primários: "Women's health", "Menopause", "Hormonal balance", "Natural supplements"
Comportamentos: Compras online de saúde, usuárias de suplementos
Lookalike: 1-3% da base de clientes (quando disponível)
Evitar: Audiências muito amplas sem interesse em saúde

### Alpha Pulse (Homens 40-65, saúde prostática/vitalidade)
Interesses primários: "Men's health", "Prostate health", "Testosterone", "Vitality"
Comportamentos: Compras de suplementos masculinos, interesse em saúde preventiva
Frequência máxima por público: 3.5 (acima = saturação)

## Criativos — Padrões que Funcionam em Saúde (Brasil)

### Estrutura Vencedora
1. Hook (1-3s): Problema específico e reconhecível ("Acorda às 3h com calor intenso?")
2. Agitação: Amplificar o problema (sem exagero)
3. Solução: Produto como resposta natural (sem claims médicos)
4. Prova: Depoimento ou dado de eficácia (sem antes/depois explícito)
5. CTA: Direto para WhatsApp ("Converse com nossa especialista agora")

### Restrições Meta para Saúde (CRÍTICO)
- PROIBIDO: "cura", "elimina completamente", "100% garantido"
- PROIBIDO: Claims de tratamento médico
- PROIBIDO: Imagens antes/depois explícitas
- PERMITIDO: "Desenvolvido com extratos naturais", "Suporte ao equilíbrio hormonal"
- PERMITIDO: Depoimentos reais (sem claims de cura)
- Taxa de reprovação alta em saúde feminina → monitorar aprovação dos primeiros anúncios

### Fadiga de Criativo
- Frequência > 3.5 = criativo fatigado → pausar anúncio específico, não o ad set
- CTR caindo > 30% = sinal de fadiga (não necessariamente frequência alta)
- Ciclo de vida típico: 7-21 dias por criativo em nichos de saúde

## Budget e Bidding

### Distribuição de Budget por Fase
- Dias 1-3 (teste): Budget mínimo por ad set (R$30-50/dia). NÃO otimizar.
- Dias 4-7 (aprendizado): Dobrar budget nos ad sets com CPL < R$25.
- Dias 7+ (escala): CBO em cima dos vencedores. Budget total ÷ ad sets campeões.

### Estratégias de Bid (Meta)
- **Lowest Cost (sem bid cap):** Padrão. Deixar Meta aprender. Melhor para fase inicial.
- **Bid Cap:** Usar quando CPL estabilizar e quiser controlar custo máximo por lead.
  Risco: volume pode cair se bid cap muito agressivo.
- **Cost Cap:** Meta tenta manter CPL abaixo do cap. Mais estável que bid cap.
  Recomendado para ad sets que passaram da fase de aprendizado.

### Regra dos 50 Cliques
- Nunca otimizar ou pausar antes de 50 cliques no ad set.
- Fase de aprendizado da Meta: precisa de 50 eventos de otimização por semana.
- Para Lead Generation: 50 leads/semana por ad set para sair do aprendizado.

## CPM — Benchmarks Brasil (Saúde)

| Público | CPM Esperado |
|---------|-------------|
| Mulheres 45-60, saúde | R$18-35 |
| Homens 40-65, saúde | R$15-28 |
| Lookalike 1-3% | R$20-40 |
| Remarketing quente | R$8-15 |

CPM > 2x benchmark = problema de segmentação ou política de conteúdo.

## Algoritmo Meta — Sinais de Entrega

### Sinais positivos (o que o algoritmo premia)
- Alta taxa de clique no link (CTR > 2%)
- Alta taxa de envio de mensagem (Click-to-WhatsApp rate > 5%)
- Baixo custo por resultado vs histórico da conta
- Alta relevância de anúncio (engagement: curtidas, comentários, compartilhamentos)
- Consistência de budget (não pausar/reativar frequentemente)

### Sinais negativos (o que o algoritmo penaliza)
- Alta frequência com CTR caindo
- Muitas reclamações ou ocultações de anúncio
- Pausas frequentes e reativações (prejudica fase de aprendizado)
- CPM subindo sem resultado proporcional

## Automação e IA — Boas Práticas

### O que automatizar (safe)
- Pausas por threshold (CPL, CTR, frequência) — regras determinísticas
- Ajustes de bid ±20% dentro de guardrails
- Relatórios diários formatados
- Alertas de anomalia (budget consumido cedo, CPL explodindo)

### O que NUNCA automatizar sem aprovação
- Upload de novos criativos
- Criação de campanhas novas
- Aumento de budget além do aprovado
- Mudança de objetivo de campanha

### Recalibração de Thresholds
- Após 7 dias e ≥ 500 cliques: recalcular CPL médio real
- Novo threshold = percentil 75 dos dados (conservador)
- Comunicar ao Kaue antes de aplicar novos thresholds

## Integração WhatsApp (Click-to-WhatsApp Ads)

### Como funciona
- Anúncio → clique → abre conversa no WhatsApp diretamente
- Meta rastreia "messaging_conversation_started_7d" como evento
- Sem pixel necessário — Meta usa o evento de início de conversa

### Otimização
- Objetivo: "Mensagens" ou "Conversas iniciadas"
- Meta usa este evento para encontrar usuários mais propensos a iniciar chat
- SDR (Lívia) responde a conversa — qualidade da resposta impacta qualidade da audiência Meta aprendeu

### Rastreamento (sem pixel)
- Usar UTM parameters no link do WhatsApp
- Registrar conversas iniciadas por ad set no CRM
- Calcular CPL manualmente: gasto ÷ conversas qualificadas
