# Playbooks Meta Ads - Ratos de IA e InsightfulPipe

Esta base adapta padroes uteis das referencias Meta Ads Ratos e InsightfulPipe para o
Caio gestor de trafego da Raiz Vital. O objetivo e orientar diagnostico, auditoria,
planejamento e solicitacoes de aprovacao. Nao substitui guardrails de budget nem
autorizacao humana.

## Principios operacionais

- Primeiro diagnosticar, depois agir.
- Antes de atribuir resultado a uma campanha, quebrar dados por campanha, ad set e ad.
- Toda criacao ou duplicacao deve nascer `PAUSED`.
- Ativacao, delecao, novo criativo, nova campanha, novo ad set e aumento de budget
  acima do limite exigem aprovacao do Kaue.
- Mudancas de budget precisam ser comunicadas em reais e em centavos de API.
- Criativos da Meta podem ser imutaveis para URL, `url_tags` e post organico; quando
  houver correcao de tracking, a abordagem segura e duplicar com criativo novo,
  validar preview, ativar o novo e pausar o antigo.
- Sempre validar preview antes de considerar um criativo pronto.
- Nunca operar com dados insuficientes: minimo de 50 cliques para acao tatica e 500
  cliques para decisoes de escala.

## Matriz de skills adaptadas

### Account auditor

Use quando precisar auditar a conta Meta Ads antes de escalar ou depois de queda de
performance.

Checar:

- campanhas ativas, pausadas e reprovadas;
- distribuicao de budget por produto e campanha;
- ad sets com gasto sem leads;
- ad sets com menos de 50 cliques;
- frequencia alta e queda de CTR;
- historico de atividades recentes;
- pixels/datasets disponiveis e sinais recentes;
- audiencias custom/lookalike existentes.

Saida esperada:

- resumo executivo;
- riscos criticos;
- oportunidades de melhoria;
- acoes autonomas permitidas;
- acoes que exigem aprovacao.

### Performance analyzer

Use quando receber pedido de diagnostico de resultado, CPL alto, queda de leads ou
decisao de escala.

Sempre segmentar por:

- campanha;
- ad set;
- anuncio;
- criativo;
- quando disponivel, breakdown por idade, genero, plataforma, posicionamento e pais.

Interpretacao:

- CPL alto com CTR baixo tende a indicar problema de criativo, hook ou oferta.
- CPL alto com CTR bom tende a indicar desalinhamento pos-clique, WhatsApp ou
  qualificacao.
- CPM muito alto pode indicar segmentacao ruim, audiencia saturada ou politica.
- Frequencia acima de 3.5 com CTR em queda indica fadiga criativa.

### Budget allocator

Use para recomendar redistribuicao de verba. O Caio nao aumenta budget total sem
aprovacao.

Regras:

- proteger campanhas/ad sets campeoes com CPL baixo, CTR alto e ROAS sustentado;
- reduzir ou pausar gasto em ad sets criticos apos dados suficientes;
- nao mover budget para ad sets sem volume minimo;
- propor mudancas em etapas, evitando saltos bruscos;
- registrar impacto esperado em leads, CPL e gasto diario.

### Campaign structure

Para a Raiz Vital:

- 1 campanha por produto quando houver volume suficiente: New Woman e Alpha Pulse.
- Usar ABO em fase inicial sem historico; avaliar CBO quando houver pelo menos 3 ad
  sets com historico consistente.
- Separar publico frio, lookalike e remarketing quando os dados existirem.
- Nao misturar produtos, promessas ou audiencias incompativeis no mesmo ad set.

### Creative tester

Use para planejar testes de criativos sem baguncar o aprendizado da Meta.

Variaveis a isolar:

- hook;
- angulo da dor;
- prova/depoimento;
- CTA;
- formato: imagem, video, UGC, carrossel.

Regras:

- testar uma variavel principal por vez;
- manter budget minimo suficiente;
- nao pausar antes de 50 cliques, salvo reprovacao ou risco de politica;
- solicitar novo criativo quando houver fadiga, CTR em queda ou frequencia alta.

### Launch checklist

Antes de ativar campanha/ad set/ad:

- campanha, ad set e ad existem e estao com status correto;
- criativo tem CTA;
- Instagram ID/Page ID estao corretos;
- `url_tags`/UTMs existem e identificam produto, campanha, ad set e criativo;
- preview foi validado nos formatos principais;
- budget e objetivo batem com o plano aprovado;
- politica de saude/suplementos foi respeitada;
- WhatsApp/SDR esta pronto para responder o volume previsto.

### Scaling roadmap

Escalar apenas quando houver:

- CPL abaixo do alvo por pelo menos 3 dias;
- CTR acima do minimo;
- ROAS ou proxy de receita sustentado;
- volume minimo de cliques/leads;
- ausencia de fadiga criativa forte.

Padrao de escala:

- duplicar ad set campeao como `PAUSED`;
- validar targeting, budget e preview;
- pedir aprovacao quando o budget total aumentar;
- ativar gradualmente;
- monitorar nos proximos ciclos.

## Regras especificas para suplementos

- Evitar promessas de cura, tratamento ou garantia absoluta.
- Evitar antes/depois explicito.
- Usar linguagem de suporte, equilibrio, vitalidade e bem-estar.
- Depoimentos precisam evitar claims medicos.
- Reprovacao de anuncio em saude deve gerar alerta critico e revisao humana.
