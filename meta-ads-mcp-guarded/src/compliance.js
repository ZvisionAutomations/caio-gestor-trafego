/**
 * Story 094 — Compliance Health/Wellness.
 *
 * Antes de criar/editar targeting ou criativo, varre TODAS as strings dos args
 * (copy, headline, nomes, interesses) contra uma lista de termos proibidos +
 * padrões de claim (config, artefato C). Suplemento feminino é categoria
 * sensível da Meta — violação pode restringir/banir a conta.
 *
 * AC-4 fail-CLOSED: matching agressivo (normaliza acento/caixa, casa por palavra),
 * na dúvida marca violação. Modo (slicing): warn loga; enforce bloqueia. Ships warn.
 */
import fs from "node:fs";

/** Tools que carregam copy/targeting (onde faz sentido checar compliance). */
const CONTENT_TOOLS = new Set([
  "create_ad",
  "update_ad",
  "create_ad_creative",
  "create_adset",
  "update_adset",
  "create_campaign",
  "update_campaign",
]);

/** Normaliza: minúsculas + remove acentos (NFD → sem diacríticos combinantes U+0300–U+036F). */
export function normalize(text) {
  return String(text)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** Coleta recursivamente todos os valores string de um objeto/array. */
export function collectStrings(value, acc = []) {
  if (value == null) return acc;
  if (typeof value === "string") {
    acc.push(value);
  } else if (Array.isArray(value)) {
    for (const v of value) collectStrings(v, acc);
  } else if (typeof value === "object") {
    for (const v of Object.values(value)) collectStrings(v, acc);
  }
  return acc;
}

export class Compliance {
  constructor(config, deps = {}) {
    this.cfg = config.compliance;
    this.logger = deps.logger;
    this.logPath = deps.logPath ?? process.env.GUARDED_COMPLIANCE_LOG ?? null;
    this.now = deps.now ?? (() => Date.now());

    // Pré-compila os termos como regex de palavra (normalizados).
    this._termRegexes = (this.cfg.prohibited_terms || []).map((term) => ({
      term,
      re: new RegExp(`\\b${escapeRegex(normalize(term))}\\b`),
    }));
    this._claimRegexes = (this.cfg.claim_patterns || []).map((pat) => {
      try {
        return { pat, re: new RegExp(normalize(pat)) };
      } catch {
        this.logger?.warn?.(`[compliance] claim_pattern inválido ignorado: ${pat}`);
        return null;
      }
    }).filter(Boolean);
  }

  get mode() {
    return this.cfg.mode === "enforce" ? "enforce" : "warn";
  }

  /**
   * @param {string} toolName
   * @param {Record<string, unknown>} args
   * @returns {null | { content: Array<object>, isError: true }}
   */
  check(toolName, args = {}) {
    if (!CONTENT_TOOLS.has(toolName)) return null;

    const haystack = normalize(collectStrings(args).join("  "));
    const hits = [];
    for (const { term, re } of this._termRegexes) {
      if (re.test(haystack)) hits.push(`termo "${term}"`);
    }
    for (const { pat, re } of this._claimRegexes) {
      if (re.test(haystack)) hits.push(`claim "${pat}"`);
    }

    if (hits.length === 0) {
      this._log({ tool: toolName, verdict: "allow", would_block: false, hits: [] });
      return null;
    }
    return this._verdict(toolName, hits);
  }

  _verdict(toolName, hits) {
    if (this.mode === "warn") {
      this._log({ tool: toolName, verdict: "allow", would_block: true, hits });
      return null;
    }
    this._log({ tool: toolName, verdict: "block", would_block: true, hits });
    return {
      content: [
        {
          type: "text",
          text:
            `⚖️ Compliance BLOQUEOU "${toolName}" (política Health/Wellness da Meta).\n` +
            `Detectado: ${hits.join("; ")}.\n` +
            `Ajuste a copy/targeting (sem alvo por condição de saúde, sem claim de cura/antes-depois) e tente de novo.`,
        },
      ],
      isError: true,
    };
  }

  _log(fields) {
    const record = { ts: new Date(this.now()).toISOString(), mode: this.mode, kind: "compliance", ...fields };
    if (fields.would_block) {
      this.logger?.warn?.(`[compliance] ${record.verdict} tool=${fields.tool} hits=${fields.hits.join(",")}`);
    }
    if (!this.logPath) return;
    try {
      fs.appendFileSync(this.logPath, JSON.stringify(record) + "\n");
    } catch (err) {
      this.logger?.warn?.(`[compliance] falha ao escrever log: ${err?.message}`);
    }
  }
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
