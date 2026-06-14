# Story 061 — Contrato documentado da pasta de handoff + exemplos (A3)

**Status:** Done
**Epic:** Caio Gestor de Tráfego — operacionalização (Raiz Vital)
**Track:** Standard (docs)
**Criada/Implementada por:** @sprint-lead + @developer — 2026-06-14
**QA:** @quality-gate — PASS (`docs/qa/gates/story-061-gate.yaml`)

## Story Statement
**As** operador da Raiz Vital, **I want** um contrato claro de como montar a pasta de handoff (estrutura + manifesto + exemplos dos 3 formatos), **so that** eu (ou o Higgsfield) consiga depositar pacotes que o Caio sobe sem erro.

## Contexto
A pasta `inbox/` não existia e não havia manifesto de exemplo. O polling (story-058) e o contrato multi-formato (story-059) já existem; faltava a **documentação de uso** + exemplos válidos, usando os valores confirmados no research CTWA (B1, `docs/research/ctwa-api-requirements.md`).

## Acceptance Criteria
- **AC-1** Documento do contrato (estrutura de pasta, campos do manifesto por seção, regras de idempotência/rejeição). ✅ `docs/handoff-folder-contract.md`
- **AC-2** Exemplos prontos dos 3 formatos (image, video, carousel), **schema-válidos**. ✅ `docs/examples/manifests/{image,video,carousel}.yaml` (validados contra `CampaignManifest`)
- **AC-3** Alinhado ao research CTWA (objetivo/optim/destination/promoted_object) + nota do CTA pendente de go-live. ✅
- **AC-4** Sem código novo; sem regressão. ✅

## Escopo
- IN: documentação + exemplos validados.
- OUT: criar a pasta `inbox/` real com assets (o operador cria ao depositar); mudança de código.

## Dev/QA Record
- Arquivos: `docs/handoff-folder-contract.md`, `docs/examples/manifests/{image,video,carousel}.yaml`, `docs/research/ctwa-api-requirements.md` (B1).
- Validação: os 3 manifestos parseiam contra o schema Pydantic (image/video single-asset, carousel 3 cards). Suíte de código inalterada (14/14).
