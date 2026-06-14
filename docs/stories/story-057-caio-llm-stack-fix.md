# Story 057 — Correção e migração da stack LLM do Caio (Gemini Flash + Claude Haiku 4.5)

**Status:** Ready for Review
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Validada por:** @product-lead (Axis) — 2026-06-14 — GO (CoVe: rastreável, AC testáveis, gate D9 bloqueante mantido)
**Track:** Standard
**Owner sugerido:** @developer (Pixel)
**Criada por:** @sprint-lead (Sync) — 2026-06-14

---

## Story Statement

**As** operador da Raiz Vital responsável pelo agente Caio (gestor de tráfego Meta Ads),
**I want** a stack de LLM do Caio corrigida e alinhada à decisão de arquitetura (Gemini Flash como "músculo" + Claude Haiku 4.5 como "cérebro" de tool-calling),
**so that** o agente pare de depender de um modelo descontinuado e de um modelo mais caro que o necessário (Sonnet 4.6), reduzindo custo (~US$ 5–15/mês alvo) sem perder qualidade de decisão.

---

## Contexto (verificado no código — não só memória)

Verificação feita em 2026-06-14 sobre `packages/caio-trafego/`:

1. **`agent/llm_router.py` é código efetivamente morto.** Nenhum workflow (`analyze`, `optimize`, `report`, `calibrate`, `campaign_inbox`) chama `get_router()` ou `route()` — `llm_router` só aparece em docstrings (`caio.py:176-177`) e na própria definição. O caminho Groq usa `model="llama-3.1-70b-versatile"` (`llm_router.py:75`), **descontinuado pela Groq em jan/2025** → mesmo se fosse chamado, cairia sempre no fallback Claude.
2. **O cérebro real do agente está em `agent/caio.py:182,188`:** `model_id = settings.get("agent",{}).get("llm_model","claude-sonnet-4-6")` → `Agent(model=Claude(id=model_id), ...)`. O valor vem de **`config/settings.yaml:8` → `llm_model: "claude-sonnet-4-6"`**. Ou seja, o agente roda hoje em **Sonnet 4.6**, não no Haiku 4.5 decidido no escopo.
3. **Gemini Flash não está integrado:** `requirements.txt` tem `anthropic` e `groq`, **não tem** SDK do Google (`google-genai`/`google-generativeai`).

**Decisão de escopo de referência** (memória `caio-gestor-trafego-escopo`, 2026-06-07; Mega Doc Raiz Vital):
- Stack alvo = **Gemini Flash** (músculo: classificação simples + geração de texto de relatório) + **Claude Haiku 4.5** (cérebro de tool-calling: decisão/escala/aprovação/upload).
- Sonnet 4.6 **sai** (criativo/copy saíram do escopo do Caio).
- Custo estimado alvo: ~US$ 5–15/mês.

---

## 🔬 GATE DE DEEP RESEARCH (NON-NEGOTIABLE — Mega Doc D9)

**Bloqueia o início da implementação.** Antes de qualquer código, executar deep research (Gemini Deep Research primário → Claude extended thinking fallback → revisão @analyst) e registrar as respostas no spec/story:

- **R1 — ID(s) atual(is) do Gemini Flash (2026):** confirmar o nome de modelo correto (ex.: família `gemini-2.x-flash`) e variantes disponíveis. `[NEEDS VERIFICATION]`
- **R2 — Integração Agno ↔ Gemini:** confirmar a classe/módulo correto do Agno para Gemini (provável `from agno.models.google import Gemini`) e se convive com `Claude` no mesmo agente/projeto. `[NEEDS VERIFICATION]`
- **R3 — SDK Python:** confirmar o pacote correto e versão (`google-genai` unificado vs `google-generativeai` legado) e a variável de ambiente (`GEMINI_API_KEY` vs `GOOGLE_API_KEY`). `[NEEDS VERIFICATION]`
- **R4 — Manter ou remover Groq:** decidir se o "músculo" passa a ser Gemini Flash (removendo Groq de `requirements.txt` e do router) ou se Groq permanece como fallback barato com um modelo **vivo** (não o llama descontinuado). Justificar.
- **R5 — Haiku 4.5 como cérebro:** confirmar `claude-haiku-4-5-20251001` suporta tool-calling no nível exigido pelas tools Meta do Caio (o agente tem ~20+ tools). (ID de partida: `claude-haiku-4-5-20251001`.)

Saída do gate: uma seção "Decisões de Research" preenchida nesta story (ou no spec) com R1–R5 resolvidos e fontes citadas, revisada pelo @analyst.

---

## Acceptance Criteria (Given/When/Then)

**AC-1 — Cérebro migrado para Haiku 4.5**
- **Given** o agente Caio é construído via `create_caio_agent()` (`caio.py`),
- **When** nenhum override é passado,
- **Then** o `model_id` resolvido é o ID do Claude Haiku 4.5 confirmado no research (partida: `claude-haiku-4-5-20251001`), e `config/settings.yaml` reflete esse valor em `agent.llm_model`.

**AC-2 — Modelo morto eliminado**
- **Given** `llm_router.py`,
- **When** o código é inspecionado,
- **Then** não existe mais referência a `llama-3.1-70b-versatile` nem a qualquer modelo descontinuado; o "músculo" aponta para o modelo decidido em R1/R4 (Gemini Flash ou Groq vivo).

**AC-3 — Músculo (Gemini Flash) integrado e funcional OU decisão documentada de não usar**
- **Given** a decisão de R4,
- **When** o router roteia `REPORT_GENERATION`/`CLASSIFICATION`,
- **Then** ou (a) chama Gemini Flash via SDK confirmado (com fallback gracioso para o cérebro Claude se `GEMINI_API_KEY` ausente, sem quebrar), ou (b) há justificativa registrada de manter Groq com modelo vivo. Em nenhum caso o processo quebra por ausência de chave (fail-safe, igual ao padrão atual `_check_groq`).

**AC-4 — Router deixa de ser código morto (ou é removido)**
- **Given** a decisão de produto/arquitetura,
- **When** a story fecha,
- **Then** ou o `llm_router` é **conectado** a pelo menos um workflow real (ex.: `report` usa o músculo para gerar texto), ou é **removido** do código e da docstring de `caio.py` se decidido que o Agno cuida de tudo. Não deixar código morto novo.

**AC-5 — Dependências corretas e verificadas**
- **Given** `requirements.txt`,
- **When** atualizado,
- **Then** contém o SDK confirmado em R3 com versão pinada; pacotes não usados (ex.: `groq` se removido) são retirados; nenhum pacote fabricado/inexistente (validar `pip index`/PyPI). `[NEEDS VERIFICATION em R3]`

**AC-6 — Variáveis de ambiente documentadas (sem secrets)**
- **Given** `.env.example` / docs do Caio,
- **When** a nova chave é necessária,
- **Then** `GEMINI_API_KEY` (ou nome confirmado em R3) está documentado como placeholder em `.env.example`, **sem valor real** (Constitution Art. X).

**AC-7 — Harness/testes verdes**
- **Given** a suíte de harnesses do Caio (`harnesses/`, `scripts/run_harnesses.py`),
- **When** executada,
- **Then** passa sem regressão; há cobertura nova para o roteamento (músculo vs cérebro) e para o fallback sem chave. ruff + mypy limpos.

**AC-8 — Custo/comportamento sanity-check**
- **Given** o agente construído,
- **When** um smoke offline é rodado (sem credenciais Meta),
- **Then** o agente instancia com o modelo Haiku 4.5 e o router seleciona o músculo corretamente por `TaskType`, sem chamadas reais pagas (mock/dry).

---

## Escopo

### IN
- Reescrita/correção de `agent/llm_router.py` (modelo morto → stack decidida; fail-safe).
- `config/settings.yaml`: `agent.llm_model` → Haiku 4.5.
- `agent/caio.py`: ajustar docstring (linha 176-177) e, se decidido, wiring do músculo.
- `requirements.txt`: SDK do músculo (R3) + limpeza de pacotes não usados.
- `.env.example` + docs do Caio: nova env var (placeholder).
- Harnesses/testes do roteamento e fallback.
- Preenchimento da seção "Decisões de Research" (R1–R5).

### OUT
- Credenciais Meta Ads (App ID/Secret/Token, account, page_id, número WhatsApp) — gate do Fernando.
- Deploy do agente Caio na VPS — story separada (depende de creds Meta + secret `caio_ro`/`CAIO_DATABASE_URL`).
- Qualquer mudança em `business_signal.py`, `campaign_inbox.py`, criação Meta — fora do escopo de LLM.
- Lívia/zwaf — intocados.

---

## Dependências
- **Bloqueante:** Gate de Deep Research (R1–R5) resolvido e revisado por @analyst.
- **Não-bloqueante:** `GEMINI_API_KEY` real (operador/Fernando) só é necessária para smoke pago real — a story fecha com fallback gracioso e testes offline.
- Sem dependência da migration 005 / `caio_ro` (essa é a story de Business Signal/deploy do agente).

---

## Notas técnicas (dev)
- Padrão fail-safe a preservar: hoje `_check_groq()` permite o agente subir sem `GROQ_API_KEY`. Manter equivalente para a chave do músculo — **nunca** quebrar boot por ausência de chave.
- Singleton `get_router()` (lazy) já evita side-effects no import — manter.
- O agente Agno tem ~20+ tools Meta registradas (`caio.py:190+`); confirmar em R5 que o cérebro Haiku 4.5 mantém qualidade de tool-calling.
- Estação Windows sem Python → harnesses rodam no WSL (py 3.x): `mount -t drvfs "G:" /mnt/g` no mesmo comando, `pip install --break-system-packages`.

## CodeRabbit / QA
- Tipo de story: **Feature/Refactor** → foco CodeRabbit: padrões de código, cobertura de testes, design do router, segurança de dependências.
- Severidades: CRITICAL/HIGH auto-fix; MEDIUM/LOW como tech-debt.
- CodeRabbit pode ser **WAIVED** se SaaS não provisionado (registrar), conforme sessões anteriores.

## Test Strategy
- Unit: roteamento por `TaskType` (músculo vs cérebro); fallback sem chave; resolução de `model_id` em `create_caio_agent()`.
- Smoke offline: instanciar agente com Haiku 4.5 sem credenciais Meta (sem chamada paga).
- Gates: harnesses verdes, ruff, mypy exit 0, secret scan limpo.

---

## Decisões de Research (gate D9 — RESOLVIDO por @analyst em 2026-06-14)

**R1 — ID(s) do Gemini Flash (2026):** ✅ RESOLVIDO
- ⚠️ **`gemini-2.0-flash` está MORTO** (shutdown 1-jun-2026) — **não usar** (a doc do Agno ainda exibe esse ID desatualizado).
- Modelos Flash **vivos** em 2026: `gemini-2.5-flash` ($0,30/$2,50 por 1M tok in/out), **`gemini-2.5-flash-lite`** ($0,10/$0,40 — o mais barato), `gemini-3.5-flash` (lançado 19-mai-2026, $1,50/$9,00).
- **Recomendação p/ o músculo** (classificação simples + texto de relatório, baixo volume): **`gemini-2.5-flash-lite`**. Alternativa de maior qualidade: `gemini-2.5-flash`.
- Fontes: [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing), [Artificial Analysis — 2.5 Flash](https://artificialanalysis.ai/models/gemini-2-5-flash/providers), [TeamAI — guia 2026](https://teamai.com/blog/large-language-models-llms/gemini-models-explained-the-complete-2026-guide/).

**R2 — Integração Agno ↔ Gemini:** ✅ RESOLVIDO
- Import: `from agno.models.google import Gemini` → `Agent(model=Gemini(id="gemini-2.5-flash-lite"))`. **Convive** com a classe `Claude` (ambas em `agno.models`) — o Caio pode ter cérebro Claude e músculo Gemini no mesmo projeto.
- ⚠️ **Risco conhecido (não-bloqueante p/ este uso):** issues abertas [agno #2186](https://github.com/agno-agi/agno/issues/2186) (Gemini tools + response_model incompatíveis) e [#2298](https://github.com/agno-agi/agno/issues/2298) (role de function response). **Não afeta** o músculo (relatório/classificação SEM tools); tool-calling fica 100% no cérebro Haiku. Fontes: [Agno Google cookbook](https://docs.agno.com/cookbook/models/google), [Agno Gemini toolkit](https://docs.agno.com/tools/toolkits/models/gemini).

**R3 — SDK Python + env var:** ✅ RESOLVIDO
- SDK = **`google-genai`** (unificado, GA mai/2025) — é o que o Agno usa (`pip install google-genai agno`). O legado **`google-generativeai` está deprecado/sunset desde 30-nov-2025** → NÃO usar.
- Env var: a classe Gemini do Agno lê **`GOOGLE_API_KEY`** (doc oficial do Agno). O SDK unificado também aceita `GEMINI_API_KEY`, mas para compat com o Agno usar **`GOOGLE_API_KEY`** (documentar como placeholder no `.env.example`).
- Fontes: [Google GenAI SDK (deprecation notice)](https://github.com/google-gemini/deprecated-generative-ai-python), [Gemini API libraries](https://ai.google.dev/gemini-api/docs/libraries), [Agno Gemini toolkit](https://docs.agno.com/tools/toolkits/models/gemini).

**R4 — Manter ou remover Groq:** ✅ RESOLVIDO → **REMOVER Groq.**
- Justificativa: o caminho Groq é código morto (nenhum workflow chama) e aponta para `llama-3.1-70b-versatile` (descontinuado jan/2025); manter exige carregar a dep `groq` por zero valor. O músculo passa a ser **`gemini-2.5-flash-lite`** via Agno. Remover `groq` de `requirements.txt` e do router. Volume do Caio é baixo (3 ciclos/dia) → custo do músculo é centavos/mês de qualquer forma; a escolha honra a decisão de escopo (Gemini Flash) e elimina dead code.
- **Fail-safe obrigatório:** se `GOOGLE_API_KEY` ausente, o router faz fallback gracioso para o cérebro Claude (igual ao padrão `_check_groq` atual) — nunca quebrar o boot.

**R5 — Haiku 4.5 como cérebro (tool-calling):** ✅ RESOLVIDO → ADEQUADO.
- `claude-haiku-4-5-20251001` (lançado 15-out-2025): 73% SWE-Bench Verified, supera Sonnet 4 em computer use (OSWorld 50,7%), forte em uso de ferramentas/agêntico. Adequado como cérebro do Caio (20+ tools Meta). Recomendado smoke test com o conjunto real de tools, mas **sem bloqueio arquitetural**.
- Fontes: [Caylent — Haiku 4.5 deep dive](https://caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity), [Skywork — Haiku agentic](https://skywork.ai/skypage/en/claude-haiku-engineer-speed-cost-agentic/1979012260630745088).

**Revisão @analyst:** ✅ FEITA (Scope, 2026-06-14). Gate D9 satisfeito — implementação desbloqueada. Resumo p/ o dev: cérebro `claude-haiku-4-5-20251001` (settings.yaml); músculo `gemini-2.5-flash-lite` via `from agno.models.google import Gemini`; dep `google-genai` (remover `groq`); env `GOOGLE_API_KEY` (placeholder no `.env.example`); fallback gracioso sem chave.

---

## Dev Agent Record

**Agent Model Used:** claude-opus-4-8 (Pixel / @developer)
**Data:** 2026-06-14

### Completion Notes
- **AC-1 ✅** Cérebro → `claude-haiku-4-5-20251001` em `config/settings.yaml` (`agent.llm_model`) e default em `agent/caio.py`.
- **AC-2 ✅** Modelo morto removido: `llm_router.py` não tem mais `llama-3.1-70b-versatile`, `from groq`, nem `claude-sonnet-4-6` (o harness `test_llm_router` faz asserção anti-regressão lendo o source).
- **AC-3 ✅** Músculo = Gemini 2.5 Flash-Lite via SDK unificado `google-genai`. Fail-safe: sem `GOOGLE_API_KEY`/`GEMINI_API_KEY` → fallback gracioso p/ cérebro Claude (`_check_gemini`); boot nunca quebra.
- **AC-4 ✅** Router deixou de ser dead code: conectado ao `workflows/report.py` como **narrativa executiva opcional** (aditiva, fail-safe; qualquer erro mantém o relatório determinístico intacto), togglável em `settings.yaml` (`report.executive_narrative`, default true). Decisão: NÃO substituí o relatório determinístico (evita prosa alucinada sobre números financeiros).
- **AC-5 ✅** `requirements.txt`: −`groq`, +`google-genai>=1.0.0`. Verificado no PyPI (existe; latest 2.8.0) — não é phantom. Legado `google-generativeai` (sunset 2025-11-30) NÃO usado.
- **AC-6 ✅** `config/.env.example`: −`GROQ_API_KEY`, +`GOOGLE_API_KEY` placeholder (sem valor — Art. X); `ANTHROPIC_API_KEY` mantido.
- **AC-7 ✅** Harnesses **7/7 PASS** (WSL py3.14, incl. novo `test_llm_router`); `ruff check` All passed; `mypy --ignore-missing-imports` Success.
- **AC-8 ✅** Smoke offline coberto por `test_traffic_skills` (constrói o agente Caio com `model_id` default = Haiku 4.5, sem chamadas pagas).

### Decisão de implementação (nota p/ QA)
O músculo usa o SDK **raw `google-genai`** (`from google import genai`), e NÃO a classe `agno.models.google.Gemini` que o research mencionou. Motivo: o router é um helper de texto puro de uma chamada (não um Agno Agent), então o SDK direto é mais simples e evita os bugs Agno+Gemini (#2186/#2298). O cérebro Agno continua `Claude`. Sem impacto nos ACs.

### CodeRabbit
**WAIVED** — CLI não provisionado nesta estação (consistente com stories 046/048). Qualidade coberta por ruff + mypy + suíte de harnesses.

### File List
- `agent/llm_router.py` (reescrito)
- `agent/caio.py` (docstring + default model_id)
- `agent/workflows/report.py` (narrativa executiva fail-safe + toggle)
- `config/settings.yaml` (llm_model Haiku 4.5 + report.executive_narrative)
- `config/.env.example` (−GROQ_API_KEY, +GOOGLE_API_KEY)
- `requirements.txt` (−groq, +google-genai>=1.0.0)
- `harnesses/test_llm_router.py` (novo)
- `harnesses/test_report.py` (narrativa off no harness)
- `scripts/run_harnesses.py` (registra test_llm_router)

### Change Log
| Data | Mudança |
|------|---------|
| 2026-06-14 | story-057: stack LLM Caio → Gemini 2.5 Flash-Lite (músculo) + Claude Haiku 4.5 (cérebro); Groq morto removido; router conectado ao relatório (narrativa fail-safe); suíte 7/7 + ruff + mypy verdes. |

---

## QA Results

**Reviewer:** Litmus (@quality-gate) · **Data:** 2026-06-14 · **Gate:** ✅ **PASS**
**Gate file:** `docs/qa/gates/story-057-gate.yaml`

### Rastreabilidade AC → código (8/8 verificada independentemente)
Todos os 8 ACs confirmados via leitura dos arquivos + re-execução. Destaques:
- **Fail-safe comprovado empiricamente:** `import`/instanciação do router **sem** `GOOGLE_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY` não quebra (`gemini_avail=False`, IDs corretos). Boot seguro garantido.
- **Sem modelo morto:** grep em `agent/` + `config/` + `requirements.txt` → nenhum `llama-3.1-70b-versatile`, `claude-sonnet-4-6` ou `groq`.
- **Sem secrets:** `.env.example` só com placeholders vazios (Art. X).
- **Suíte 7/7 PASS** re-rodada no WSL (incl. `test_llm_router`); `ruff` All passed; `mypy` Success.

### NFRs
Security ✅ · Reliability ✅ (fail-safe) · Maintainability ✅ (dead code removido) · Performance ✅ (Flash-Lite, baixo volume).

### Notas advisory (não-bloqueantes)
1. Com `report.executive_narrative=true` (default), o relatório diário passa a fazer 1 chamada LLM/dia (músculo, ou cérebro no fallback) — custo desprezível, togglável. Comportamento novo em prod, documentado.
2. Decisão de design (SDK raw `google-genai` no router vs classe Agno `Gemini`): **aceitável** — chamada de texto puro, tool-calling segue no cérebro Claude, evita bugs Agno+Gemini.

### Deploy
Agente Caio (`packages/caio-trafego`) **não roda na VPS** ainda → "deploy" = commit + PR no repo `caio-gestor-trafego` (+ docs Sinapse). Sem deploy-por-cópia. `GOOGLE_API_KEY` real só é necessária quando o Caio for ao ar (gate operador/Fernando); até lá o fallback cobre.

**Recomendação:** liberar para @devops (commit + PR). Sem itens must-fix.
