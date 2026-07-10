/**
 * Story 089 — reconciler (furo B do slicing).
 *
 * As transições reais são dirigidas por LEITURA de insight (um adset SAI de
 * learning por tempo/eventos; FADIGA por freq/CTR), não por uma tool call nossa.
 * Um cron nativo do Hermes (junto dos ciclos 08/14/20:30) chama o reconciler:
 * lê get_insights, mapeia cada adset → estado alvo, e ESCREVE no store.
 *
 * `reconcile()` é puro (recebe as rows já lidas + store) → testável. O runner que
 * chama get_insights via MCP filho é verificado na VPS.
 */
import { mapSignalToState, canTransition } from "./state_machine.js";

/**
 * @param {Array<{ adset_id: string, label?: string, days_active?: number }>} signals
 * @param {{ getState: Function, setState: Function }} store
 * @param {{ logger?: object }} [ctx]
 * @returns {Promise<{ evaluated: number, transitioned: number, changes: Array }>}
 */
export async function reconcile(signals, store, ctx = {}) {
  let transitioned = 0;
  const changes = [];
  for (const sig of signals) {
    if (!sig || !sig.adset_id) continue;
    const target = mapSignalToState(sig);
    const current = await store.getState(sig.adset_id);
    const from = current?.state ?? null;

    if (from === target) continue; // já no estado alvo
    if (from && !canTransition(from, target)) {
      ctx.logger?.warn?.(`[reconciler] transição inválida ${from}→${target} p/ ${sig.adset_id} (ignorada)`);
      continue;
    }
    await store.setState(sig.adset_id, target, { reason: `reconciler: ${sig.label ?? "n/a"}` });
    transitioned += 1;
    changes.push({ adset_id: sig.adset_id, from, to: target });
  }
  return { evaluated: signals.length, transitioned, changes };
}

/**
 * Runner: lê get_insights via MCP filho, extrai o sinal por adset e reconcilia.
 * Verificado na VPS (assinatura exata de get_insights confirma lá). Tolerante a
 * formatos: tenta achar rows com adset_id + métricas.
 *
 * @param {{ callTool: Function }} childClient
 * @param {object} store
 * @param {{ logger?: object, extractSignals?: Function }} [ctx]
 */
export async function runReconcile(childClient, store, ctx = {}) {
  const extract = ctx.extractSignals ?? defaultExtractSignals;
  let raw;
  try {
    raw = await childClient.callTool({ name: "get_insights", arguments: { level: "adset", date_preset: "last_7d" } });
  } catch (err) {
    ctx.logger?.warn?.(`[reconciler] get_insights falhou (${err?.message}); ciclo pulado.`);
    return { evaluated: 0, transitioned: 0, changes: [] };
  }
  const signals = extract(raw);
  return reconcile(signals, store, ctx);
}

/** Extrai [{adset_id,label,days_active}] do retorno do get_insights (best-effort). */
export function defaultExtractSignals(toolResult) {
  const text = toolResult?.content?.map?.((c) => c.text).join("\n") ?? "";
  try {
    const data = JSON.parse(text);
    const rows = Array.isArray(data) ? data : data.data || data.insights || [];
    return rows
      .filter((r) => r && (r.adset_id || r.adset_id === 0))
      .map((r) => ({ adset_id: String(r.adset_id), label: r.label, days_active: r.days_active }));
  } catch {
    return []; // formato inesperado → nada a reconciliar (fail-safe)
  }
}
