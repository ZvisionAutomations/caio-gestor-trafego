/**
 * Carga do config de guardrails (artefato C — hermes-v2-slicing §1).
 *
 * Config-driven: thresholds/listas/flags do wrapper vivem num YAML editável
 * pelo operador SEM redeploy. Fonte única de números (furo D do slicing): o
 * SOUL-v2 só referencia; os valores só vivem aqui.
 *
 * Fail-safe: se o arquivo não existir ou for inválido, usa DEFAULTS seguros
 * (nunca derruba o boot do proxy).
 */
import fs from "node:fs";
import { parse as parseYaml } from "yaml";

/** Defaults seguros — teto base R$300, modo warn (7 dias antes de enforce). */
export const DEFAULT_CONFIG = {
  guardian: {
    mode: "warn", // warn | enforce
    base_daily_cap: 300, // BRL — teto base da conta (AC-1/AC-6)
    reinvest_pct: 0.2, // AC-6: teto dinâmico = base + pct × receita_atribuída
    max_daily_per_adset: 50, // BRL — teto por adset (AC-1)
    max_mutations_per_hour: 12, // anti-flapping (slicing)
    circuit_breaker: {
      consecutive_blocks_to_trip: 5,
      cooldown_minutes: 30,
    },
  },
  state: {
    mode: "warn", // warn | enforce (story-089 — gate de consistência de estado)
  },
  rules: {
    // story-090 — thresholds tunáveis sem redeploy (AC-1). BRL/horas/dias.
    cpl_target_brl: 40, // CPL-alvo por Purchase
    cpl_proxy_brl: 14, // CPL proxy (conversa/lead)
    min_window_hours: 72, // janela mínima antes de agir (ciclo WhatsApp)
    pause_min_spend_brl: 50, // gasto mínimo p/ considerar pausa (AC-2)
    freq_max: 3.5, // frequência máxima antes de fadiga/pausa
    scale_pct: 0.2, // incremento de escala (+20% / 72h)
    scale_jump_duplicate_factor: 2, // salto > 2× → duplicar adset (não editar)
    scale_min_days_profitable: 7, // AC-3.1 — dias lucrativos consecutivos p/ escala autônoma
    fatigue_ctr_drop_pct: 0.2, // queda de CTR sem/sem que sinaliza fadiga
    kill_spend_brl: 120, // gasto sem conversão que dispara kill (AC-5)
    kill_max_days: 14, // idade máxima sem conversão
  },
  retargeting: {
    // story-093 — Campanha 2 (ABO) de conversas sem compra. Números tunáveis sem redeploy.
    audience_retention_days: 14, // janela do público de conversas (AC-1)
    min_daily_budget_brl: 30, // faixa de budget do Adset C (AC-1)
    max_daily_budget_brl: 50,
    min_differentiation_pct: 0.2, // AC-4 — diferenciação mínima entre adsets da campanha
    entry_budget_min_brl: 130, // AC-2 — budget de entrada consolidado (ToF + retargeting)
    entry_budget_max_brl: 150,
    engagement_source: "messaging", // Business Messaging (conversas WhatsApp)
    purchasers_audience_id: "", // opcional — audiência de compradores p/ exclusão (senão vem do manifest)
  },
  compliance: {
    mode: "warn", // warn | enforce (story-094)
    // Termos sensíveis Health/Wellness (baseline — revisar contra política Meta; NÃO é parecer jurídico).
    prohibited_terms: [
      "menopausa",
      "climaterio",
      "reposicao hormonal",
      "hormonio",
      "hormonal",
      "fertilidade",
      "infertil",
      "libido",
      "depressao",
      "ansiedade",
      "insonia",
      "cura",
      "trata",
      "tratamento",
      "emagrece",
      "emagrecimento",
    ],
    // Padrões de claim proibidos (antes/depois pessoal, promessa de cura). Regex (string).
    claim_patterns: ["antes\\s*(e|/)?\\s*depois", "resultado garantido", "\\bcura\\b"],
  },
};

/**
 * @param {string} [configPath] caminho do guardrails.yaml (default env GUARDED_CONFIG_PATH)
 * @param {{ logger?: object }} [opts]
 * @returns {typeof DEFAULT_CONFIG}
 */
export function loadConfig(configPath = process.env.GUARDED_CONFIG_PATH, opts = {}) {
  const logger = opts.logger;
  if (!configPath) return structuredCloneConfig(DEFAULT_CONFIG);

  try {
    const raw = fs.readFileSync(configPath, "utf8");
    const parsed = parseYaml(raw) || {};
    return mergeConfig(DEFAULT_CONFIG, parsed);
  } catch (err) {
    logger?.warn?.(`config "${configPath}" não lido (${err?.message}); usando defaults seguros.`);
    return structuredCloneConfig(DEFAULT_CONFIG);
  }
}

function structuredCloneConfig(cfg) {
  return JSON.parse(JSON.stringify(cfg));
}

/** Merge raso por seção conhecida — valores do arquivo sobrescrevem os defaults. */
function mergeConfig(base, override) {
  const out = structuredCloneConfig(base);
  const g = override.guardian || {};
  Object.assign(out.guardian, sanitizeGuardian(g));
  if (g.circuit_breaker && typeof g.circuit_breaker === "object") {
    Object.assign(out.guardian.circuit_breaker, g.circuit_breaker);
  }
  const st = override.state || {};
  if (st.mode === "warn" || st.mode === "enforce") out.state.mode = st.mode;
  const r = override.rules || {};
  for (const k of Object.keys(out.rules)) {
    if (typeof r[k] === "number" && Number.isFinite(r[k])) out.rules[k] = r[k];
  }
  const rt = override.retargeting || {};
  for (const k of [
    "audience_retention_days",
    "min_daily_budget_brl",
    "max_daily_budget_brl",
    "min_differentiation_pct",
    "entry_budget_min_brl",
    "entry_budget_max_brl",
  ]) {
    if (typeof rt[k] === "number" && Number.isFinite(rt[k])) out.retargeting[k] = rt[k];
  }
  if (typeof rt.engagement_source === "string" && rt.engagement_source) {
    out.retargeting.engagement_source = rt.engagement_source;
  }
  if (typeof rt.purchasers_audience_id === "string") {
    out.retargeting.purchasers_audience_id = rt.purchasers_audience_id;
  }
  const c = override.compliance || {};
  if (c.mode === "warn" || c.mode === "enforce") out.compliance.mode = c.mode;
  if (Array.isArray(c.prohibited_terms)) {
    out.compliance.prohibited_terms = c.prohibited_terms.map(String);
  }
  if (Array.isArray(c.claim_patterns)) {
    out.compliance.claim_patterns = c.claim_patterns.map(String);
  }
  return out;
}

/** Só aceita chaves conhecidas com tipo plausível (evita config quebrada silenciosa). */
function sanitizeGuardian(g) {
  const clean = {};
  if (g.mode === "warn" || g.mode === "enforce") clean.mode = g.mode;
  for (const k of ["base_daily_cap", "reinvest_pct", "max_daily_per_adset", "max_mutations_per_hour"]) {
    if (typeof g[k] === "number" && Number.isFinite(g[k])) clean[k] = g[k];
  }
  return clean;
}
