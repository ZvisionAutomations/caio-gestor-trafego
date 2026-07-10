/**
 * Story 090 — motor de regras multi-condição (lógica pura, config-driven).
 *
 * NUNCA age por métrica única (research 2026). Recebe as métricas já lidas de um
 * adset + estado (089) + thresholds (config) e devolve UMA decisão. A execução
 * fica pro Hermes (SOUL) chamando a tool, sempre gated pelo Guardian (088) e pelo
 * state (089). Este módulo é a fonte determinística do "o que fazer".
 *
 * Prioridade: KILL > PAUSE > FATIGUE > SCALE > HOLD.
 */

/** @typedef {"kill"|"pause"|"fatigue_variant"|"scale"|"duplicate"|"hold"} Action */

/**
 * @param {object} m métricas do adset:
 *   { cpl_proxy_brl, cpl_purchase_brl, freq, hours_running, spend_brl,
 *     ctr_now, ctr_prev, conversions, days_running, hours_since_edit,
 *     days_profitable_consecutive }
 * @param {string|null} state estado 089 (LEARNING/ACTIVE/SCALING/FATIGUED/PAUSED)
 * @param {object} cfg config.rules
 * @returns {{ action: Action, autonomous: boolean, reason: string }}
 */
export function evaluateAdset(m = {}, state, cfg) {
  const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
  const cplProxy = num(m.cpl_proxy_brl);
  const cplPurchase = num(m.cpl_purchase_brl);
  const freq = num(m.freq);
  const hours = num(m.hours_running);
  const spend = num(m.spend_brl);
  const conversions = num(m.conversions);
  const daysRunning = num(m.days_running);
  const hoursSinceEdit = num(m.hours_since_edit);
  const daysProfitable = num(m.days_profitable_consecutive);

  // KILL (AC-5): gastou o teto de kill sem nenhuma conversão, ou passou da idade máxima.
  if (conversions === 0 && (spend > cfg.kill_spend_brl || daysRunning >= cfg.kill_max_days)) {
    return { action: "kill", autonomous: false, reason: `sem conversão com gasto R$${spend} / ${daysRunning}d — kill` };
  }

  // PAUSE composta (AC-2): CPL proxy >2× alvo E freq alta E >72h E gasto>piso.
  if (
    cplProxy > 2 * cfg.cpl_proxy_brl &&
    freq > cfg.freq_max &&
    hours > cfg.min_window_hours &&
    spend > cfg.pause_min_spend_brl
  ) {
    return { action: "pause", autonomous: false, reason: `CPL proxy ${cplProxy} >2×, freq ${freq}, >72h, gasto R$${spend}` };
  }

  // FATIGUE (AC-5): freq alta + CTR caindo >20% sem/sem → nova variante.
  if (freq > cfg.freq_max && m.ctr_prev > 0) {
    const drop = (num(m.ctr_prev) - num(m.ctr_now)) / num(m.ctr_prev);
    if (drop >= cfg.fatigue_ctr_drop_pct) {
      return { action: "fatigue_variant", autonomous: false, reason: `freq ${freq} + CTR caiu ${(drop * 100).toFixed(0)}% — nova variante` };
    }
  }

  // SCALE (AC-3): CPL < 0.8× alvo, >72h sem edição, fora do learning.
  const target = cplPurchase > 0 ? cplPurchase : cplProxy;
  const targetRef = cplPurchase > 0 ? cfg.cpl_target_brl : cfg.cpl_proxy_brl;
  const profitable = target > 0 && target < 0.8 * targetRef;
  if (profitable && hoursSinceEdit > cfg.min_window_hours && state && state !== "LEARNING") {
    // salto > 2× (ex.: CPL muito abaixo) → duplicar em vez de editar.
    const bigJump = target < targetRef / cfg.scale_jump_duplicate_factor;
    // AC-3.1 autonomia híbrida: autônomo só se estável+lucrativo ≥7d E fora do learning.
    const autonomous = state !== "LEARNING" && daysProfitable >= cfg.scale_min_days_profitable;
    return {
      action: bigJump ? "duplicate" : "scale",
      autonomous,
      reason: `CPL ${target} < 0.8×alvo, ${hoursSinceEdit}h sem edição, ${daysProfitable}d lucrativo${autonomous ? " (autônomo)" : " (pede aprovação)"}`,
    };
  }

  return { action: "hold", autonomous: false, reason: "sem condição multi-fator satisfeita" };
}

/**
 * AC-3.2 — incremento de escala financiado pelo reinvestimento.
 * @param {number} currentBudgetBrl
 * @param {number} receitaAtribuidaBrl receita via CAPI (087); null/0 → sem reinvest
 * @param {object} cfg config.rules (usa scale_pct)
 * @returns {number} novo budget BRL (nunca reduz)
 */
export function reinvestBudget(currentBudgetBrl, receitaAtribuidaBrl, cfg) {
  const base = Math.max(0, Number(currentBudgetBrl) || 0);
  const receita = Number(receitaAtribuidaBrl);
  if (!Number.isFinite(receita) || receita <= 0) return base; // sem sinal → sem reinvest
  return base + cfg.scale_pct * receita;
}
