# Story 062 — Artefatos de deploy do agente Caio na VPS (A2)

**Status:** Ready (artefatos prontos; deploy **bloqueado** por credenciais Meta/Kaue)
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Track:** Infra
**Criada/Implementada por:** @sprint-lead + @developer — 2026-06-14
**QA:** @quality-gate — PASS (artefatos) / deploy real pendente do gate externo

## Story Statement
**As** operador, **I want** os artefatos de deploy do agente Caio prontos (Dockerfile + serviço no compose + .env + runbook), **so that** assim que o Kaue liberar as credenciais Meta eu (ou o Claude via EC2) suba o agente sem improviso.

## Contexto
O agente Caio (`packages/caio-trafego`) é um **serviço novo** (Python/Agno + APScheduler 24/7) e **não tinha** Dockerfile/serviço na VPS (só o zwaf roda lá). Esta story entrega os artefatos; o **deploy de fato** depende das credenciais Meta (gate Kaue/Fernando).

## Acceptance Criteria
- **AC-1** `Dockerfile` (python:3.11-slim, instala requirements, `python -m agent.main`); segredos **não** entram na imagem (só `config/settings.yaml`). ✅
- **AC-2** `docker-compose.caio.yml` — serviço `caio`, volumes `inbox/`+`logs/`, rede externa do zwaf (acesso read-only ao Postgres). ✅
- **AC-3** `.dockerignore` impede `.env`/secrets/lixo na imagem. ✅
- **AC-4** `config/.env.example` completo (Meta, LLM, Evolution, **CAIO_DATABASE_URL + CAIO_SIGNAL_TENANT_ID**). ✅
- **AC-5** Runbook de deploy (`docs/deploy-caio-vps.md`) com os passos (cópia, `.env.caio` via nano, senha `caio_ro`, tetos, rede, subir, handoff, go-live check, rollback). ✅
- **AC-6** Compose YAML válido; entrypoint correto. ✅ (validado)

## Escopo
- IN: Dockerfile, compose, .dockerignore, .env.example, runbook.
- OUT: **executar** o deploy (gate Meta/Kaue); criar a pasta `inbox/` real; build/push de imagem em registry.

## Pendência (gate externo)
- Credenciais Meta (Kaue tem a senha do Meta for Developers) + tetos de budget + número WhatsApp vinculado à página. Quando chegarem: seguir `docs/deploy-caio-vps.md`. O Claude consegue executar via EC2 Instance Connect (sem .pem); só a senha do `caio_ro` é setada pelo operador/Claude na VPS (nunca no chat).
