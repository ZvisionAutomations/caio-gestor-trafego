/**
 * Story 091 — Schema validation de tool calls mutantes.
 *
 * Antes de repassar uma tool mutante ao meta-ads-mcp real, valida que os IDs
 * de objeto Meta são strings numéricas puras (o GLM-4.7-flash pode alucinar IDs
 * plausíveis mas inválidos). Fail-safe: erro NUNCA derruba o proxy — retorna um
 * objeto de erro estruturado pro LLM reformular.
 *
 * Princípios (ACs da story-091):
 *  - AC-2: adset_id / campaign_id / ad_id devem casar ^\d+$ (sem act_/adset_).
 *  - AC-4: ValidationError vira erro estruturado, nunca exceção não tratada.
 *  - AC-5: extra="allow" — só valida os campos conhecidos; campos extras passam.
 */

/** Regex de ID de objeto Meta (adset/campaign/ad/creative): string numérica pura. */
export const META_NUMERIC_ID = /^\d+$/;

/**
 * Campos que, quando presentes numa tool call, DEVEM ser ID numérico Meta.
 * `account_id` NÃO entra aqui: contas usam prefixo `act_` (formato diferente).
 */
export const NUMERIC_ID_FIELDS = new Set([
  "adset_id",
  "campaign_id",
  "ad_id",
  "creative_id",
]);

/** Versão plural (arrays de IDs numéricos). */
export const NUMERIC_ID_ARRAY_FIELDS = new Set([
  "adset_ids",
  "campaign_ids",
  "ad_ids",
]);

/**
 * Tools mutantes conhecidas do meta-ads-mcp (+ aliases do runtime legado).
 * Cada entrada lista os campos obrigatórios (presença) além dos ID numéricos,
 * que são validados por tipo onde quer que apareçam.
 *
 * Só tools MUTANTES entram aqui; read-only (get_*, search_*) fazem passthrough
 * direto sem validação (não mutam nada).
 */
export const MUTATING_TOOLS = new Map([
  // meta-ads-mcp (nomes reais do wrapper A, hermes-v2-slicing §1.1)
  ["create_campaign", { required: [] }],
  ["update_campaign", { required: ["campaign_id"] }],
  ["create_adset", { required: ["campaign_id"] }],
  ["update_adset", { required: ["adset_id"] }],
  ["create_ad", { required: ["adset_id"] }],
  ["update_ad", { required: ["ad_id"] }],
  ["create_ad_creative", { required: [] }],
  ["upload_ad_image", { required: [] }],
  // aliases do runtime legado (story-091 texto original)
  ["pause_ad_set", { required: ["adset_id"] }],
  ["duplicate_ad_set", { required: ["adset_id"] }],
  ["adjust_bid", { required: ["adset_id"] }],
]);

/**
 * @param {string} toolName
 * @returns {boolean} true se a tool muta estado e precisa de validação.
 */
export function isMutatingTool(toolName) {
  return MUTATING_TOOLS.has(toolName);
}

/**
 * Valida os argumentos de uma tool mutante.
 *
 * @param {string} toolName
 * @param {Record<string, unknown>} args
 * @returns {{ ok: true } | { ok: false, issues: Array<{field: string, expected: string, got: unknown}> }}
 */
export function validateToolArgs(toolName, args) {
  const spec = MUTATING_TOOLS.get(toolName);
  if (!spec) {
    // Não é mutante conhecida → nada a validar aqui (passthrough).
    return { ok: true };
  }

  const issues = [];
  const a = args && typeof args === "object" ? args : {};

  // 1. Campos obrigatórios presentes (AC-1).
  for (const field of spec.required) {
    if (a[field] === undefined || a[field] === null || a[field] === "") {
      issues.push({ field, expected: "obrigatório (presente e não-vazio)", got: a[field] });
    }
  }

  // 2. IDs numéricos escalares (AC-2). Valida onde aparecerem, mesmo não-obrigatórios.
  for (const field of NUMERIC_ID_FIELDS) {
    if (a[field] === undefined || a[field] === null) continue;
    const value = a[field];
    if (typeof value !== "string" || !META_NUMERIC_ID.test(value)) {
      issues.push({
        field,
        expected: "string numérica pura (^\\d+$), sem prefixo act_/adset_/etc.",
        got: value,
      });
    }
  }

  // 3. IDs numéricos em array.
  for (const field of NUMERIC_ID_ARRAY_FIELDS) {
    if (a[field] === undefined || a[field] === null) continue;
    const value = a[field];
    if (!Array.isArray(value)) {
      issues.push({ field, expected: "array de strings numéricas", got: value });
      continue;
    }
    value.forEach((item, i) => {
      if (typeof item !== "string" || !META_NUMERIC_ID.test(item)) {
        issues.push({
          field: `${field}[${i}]`,
          expected: "string numérica pura (^\\d+$)",
          got: item,
        });
      }
    });
  }

  return issues.length === 0 ? { ok: true } : { ok: false, issues };
}

/**
 * Monta o resultado de erro estruturado no formato MCP tool result (AC-4).
 * O LLM lê o texto e reformula a chamada — o proxy NÃO chama a Graph API.
 *
 * @param {string} toolName
 * @param {Array<{field: string, expected: string, got: unknown}>} issues
 * @returns {{ content: Array<{type: 'text', text: string}>, isError: true }}
 */
export function buildValidationErrorResult(toolName, issues) {
  const lines = issues.map(
    (i) => `  - campo "${i.field}": esperado ${i.expected}; recebido: ${JSON.stringify(i.got)}`,
  );
  const text = [
    `❌ Validação de schema BLOQUEOU a tool "${toolName}" antes de chamar a Meta.`,
    `Motivo: argumento(s) inválido(s) — possível ID alucinado.`,
    ...lines,
    `Corrija os campos e chame a tool de novo com IDs reais (obtidos via get_campaigns / get_adsets / get_ads).`,
  ].join("\n");
  return { content: [{ type: "text", text }], isError: true };
}
