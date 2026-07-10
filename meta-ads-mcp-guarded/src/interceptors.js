/**
 * Pipeline de interceptors do wrapper A (meta-ads-mcp-guarded).
 *
 * Ordem de execução para uma tool MUTANTE (hermes-v2-slicing §1.1):
 *   validação de schema (091) → guardian (088) → compliance (094) → state (089)
 *
 * Cada interceptor recebe (toolName, args, ctx) e retorna (sync ou async):
 *   - null  → segue pro próximo (allow)
 *   - { content, isError } → BLOQUEIA e devolve esse resultado MCP ao LLM
 */

import { isMutatingTool, validateToolArgs, buildValidationErrorResult } from "./validators.js";
import { canMutate } from "./state_machine.js";

/**
 * Interceptor 091 — validação de schema de tool call mutante.
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @returns {null | { content: Array<object>, isError: true }}
 */
export function schemaValidationInterceptor(toolName, args) {
  if (!isMutatingTool(toolName)) return null; // read-only / desconhecida → passthrough
  const result = validateToolArgs(toolName, args);
  if (result.ok) return null;
  return buildValidationErrorResult(toolName, result.issues);
}

/**
 * Interceptor 089 — gate de consistência de estado do adset.
 * Lê o estado persistido e barra mutação incoerente (ex.: escalar em LEARNING).
 * `stateMode` warn|enforce (default warn — só loga).
 * @param {{ getState: Function }} store
 * @param {string} stateMode
 */
export function makeStateInterceptor(store, stateMode = "warn") {
  return async function stateInterceptor(toolName, args, ctx) {
    const adsetId = args?.adset_id;
    if (!adsetId) return null; // sem adset alvo → nada a checar
    const record = await store.getState(adsetId);
    const verdict = canMutate(record?.state, toolName, args);
    if (verdict.allowed) return null;
    if (stateMode !== "enforce") {
      ctx?.logger?.warn?.(`[state] would_block ${toolName} em ${record?.state}: ${verdict.reason}`);
      return null;
    }
    return {
      content: [
        {
          type: "text",
          text: `🔁 State machine BLOQUEOU "${toolName}": adset em ${record?.state} — ${verdict.reason}.`,
        },
      ],
      isError: true,
    };
  };
}

/**
 * Monta a pipeline de interceptors ativa a partir do contexto.
 * @param {{ guardian?: object, compliance?: object, stateStore?: object, stateMode?: string }} [ctx]
 * @returns {Array<(toolName: string, args: object, ctx: object) => (null | object | Promise<null|object>)>}
 */
export function buildPipeline(ctx = {}) {
  const pipeline = [schemaValidationInterceptor]; // 091 sempre primeiro
  if (ctx.guardian) {
    pipeline.push((toolName, args) => ctx.guardian.check(toolName, args)); // 088
  }
  if (ctx.compliance) {
    pipeline.push((toolName, args) => ctx.compliance.check(toolName, args)); // 094
  }
  if (ctx.stateStore) {
    pipeline.push(makeStateInterceptor(ctx.stateStore, ctx.stateMode)); // 089
  }
  return pipeline;
}

/**
 * Roda a pipeline (await cada interceptor). Retorna o primeiro bloqueio, ou null.
 * Fail-safe (091 AC-4): exceção dentro de um interceptor é engolida e tratada
 * como "allow" — um guardrail que quebra NÃO pode derrubar o agente. (Bloqueio é
 * decisão explícita; erro de infra do guardrail não bloqueia.)
 *
 * @param {Array<Function>} pipeline
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @param {object} [ctx]
 * @returns {Promise<null | { content: Array<object>, isError: true }>}
 */
export async function runPipeline(pipeline, toolName, args, ctx = {}) {
  for (const interceptor of pipeline) {
    let verdict = null;
    try {
      verdict = await interceptor(toolName, args, ctx);
    } catch (err) {
      ctx.logger?.warn?.(
        `[guarded] interceptor ${interceptor.name || "anon"} lançou exceção (ignorado, fail-open): ${err?.message}`,
      );
      verdict = null;
    }
    if (verdict) return verdict;
  }
  return null;
}
