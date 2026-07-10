/**
 * Story 089 — State machine de adset (lógica pura).
 *
 * Estados (hermes-v2-slicing): LEARNING → ACTIVE → SCALING → FATIGUED → PAUSED.
 * A persistência é do `state_store.js` (DB) + `reconciler.js` (quem ESCREVE as
 * transições temporais/métricas). Este módulo é só a lógica pura: transições
 * válidas + o gate `canMutate` que o wrapper consulta antes de deixar passar
 * uma mutação (ex.: não escalar adset em LEARNING; não editar budget em learning).
 */

export const STATES = Object.freeze({
  LEARNING: "LEARNING",
  ACTIVE: "ACTIVE",
  SCALING: "SCALING",
  FATIGUED: "FATIGUED",
  PAUSED: "PAUSED",
});

/** Transições permitidas (state atual → estados alcançáveis). */
const TRANSITIONS = Object.freeze({
  LEARNING: ["ACTIVE", "FATIGUED", "PAUSED"],
  ACTIVE: ["SCALING", "FATIGUED", "PAUSED"],
  SCALING: ["ACTIVE", "FATIGUED", "PAUSED"],
  FATIGUED: ["ACTIVE", "PAUSED"], // pode reativar após refresh de criativo
  PAUSED: ["LEARNING", "ACTIVE"], // reabertura recomeça o aprendizado
});

/**
 * @param {string} from
 * @param {string} to
 * @returns {boolean} se a transição é válida.
 */
export function canTransition(from, to) {
  if (from === to) return true; // idempotente
  return (TRANSITIONS[from] || []).includes(to);
}

/** Tools que representam ESCALA (aumentar aposta). */
const SCALING_TOOLS = new Set(["duplicate_ad_set"]);
/** Tools que EDITAM budget/bid do adset. */
const BUDGET_EDIT_TOOLS = new Set(["update_adset", "adjust_bid"]);
/** Pausar é sempre permitido (ação de segurança). */
const SAFETY_TOOLS = new Set(["pause_ad_set"]);

/**
 * Gate de consistência: dada a máquina de estados, esta mutação é coerente?
 *
 * Regras (story-089 + slicing):
 *  - LEARNING: não escalar; não editar budget (deixa o aprendizado fechar). Pausar OK.
 *  - FATIGUED: não escalar (jogar budget em criativo cansado). Pausar/refresh OK.
 *  - PAUSED: não mexer em gasto (está parado). Reativar é transição, não mutação de budget.
 *  - ACTIVE/SCALING: liberado.
 *
 * @param {string} state estado atual do adset (ou null/desconhecido → libera, fail-open)
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @returns {{ allowed: boolean, reason?: string }}
 */
export function canMutate(state, toolName, args = {}) {
  if (!state || !STATES[state]) return { allowed: true }; // sem estado conhecido → não bloqueia (fail-open)
  if (SAFETY_TOOLS.has(toolName)) return { allowed: true }; // pausar sempre pode

  const isScaling = SCALING_TOOLS.has(toolName);
  const isBudgetEdit = BUDGET_EDIT_TOOLS.has(toolName) && args.daily_budget !== undefined;

  switch (state) {
    case STATES.LEARNING:
      if (isScaling) return { allowed: false, reason: "não escalar adset em LEARNING (aprendizado aberto)" };
      if (isBudgetEdit) return { allowed: false, reason: "não editar budget em LEARNING (deixa o aprendizado fechar)" };
      return { allowed: true };
    case STATES.FATIGUED:
      if (isScaling) return { allowed: false, reason: "não escalar adset FATIGUED (criativo cansado — troque o criativo)" };
      return { allowed: true };
    case STATES.PAUSED:
      if (isScaling || isBudgetEdit) return { allowed: false, reason: "adset PAUSED — reative antes de mexer em budget" };
      return { allowed: true };
    default: // ACTIVE, SCALING
      return { allowed: true };
  }
}

/**
 * Mapeia o sinal de análise (AdSetState efêmero de analyze.py: CHAMPION/GOOD/
 * ALERT/CRITICAL/INSUFFICIENT/FATIGUED) → estado persistido (AC-2). Sem duplicar
 * a análise: recebe o rótulo já calculado + dias no ar e devolve o estado alvo.
 *
 * @param {{ label?: string, days_active?: number }} signal
 * @returns {string} estado alvo
 */
export function mapSignalToState(signal = {}) {
  const label = String(signal.label || "").toUpperCase();
  const days = Number(signal.days_active ?? 0);

  if (label === "FATIGUED") return STATES.FATIGUED;
  if (label === "CRITICAL") return STATES.PAUSED; // crítico persistente → candidato a matar
  if (label === "INSUFFICIENT" || days < 3) return STATES.LEARNING; // janela de aprendizado (~72h)
  if (label === "CHAMPION") return STATES.SCALING; // performa → pode escalar
  if (label === "GOOD" || label === "ALERT") return STATES.ACTIVE;
  return STATES.ACTIVE;
}
