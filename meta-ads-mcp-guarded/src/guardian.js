/**
 * Story 088 — Guardian: circuit-breaker financeiro + hard cap.
 *
 * Interceptor determinístico no wrapper A. Antes de QUALQUER tool mutante que
 * gaste, aplica (do config, artefato C):
 *   - teto por adset (AC-1): daily_budget do arg não pode passar de max_daily_per_adset
 *   - anti-flapping (slicing): nº de mutações por hora limitado
 *   - circuit-breaker (slicing): N bloqueios seguidos → abre por um cooldown
 *   - teto de conta (AC-3/AC-6): base + reinvest_pct × receita_atribuída (fail-safe → base)
 *
 * Modo (AC-4): `warn` loga would_block SEM bloquear (7 dias); `enforce` bloqueia.
 * Decision log (furo E): TODA decisão vai pra JSONL desde o dia 1 — sem isso o
 * warn-mode é cego. Fonte pra decidir a virada warn→enforce.
 *
 * Unidades: budgets da Graph API vêm em CENTAVOS nos args; caps do config em BRL.
 */
import fs from "node:fs";

/** Tools mutantes que GASTAM (subconjunto que o guardian financeiro cobre). */
const SPEND_TOOLS = new Set([
  "create_adset",
  "update_adset",
  "create_campaign",
  "update_campaign",
  "create_ad",
  "duplicate_ad_set",
  "adjust_bid",
]);

export class Guardian {
  /**
   * @param {object} config config completo (usa config.guardian)
   * @param {{ logger?: object, logPath?: string, now?: () => number }} [deps]
   */
  constructor(config, deps = {}) {
    this.cfg = config.guardian;
    this.logger = deps.logger;
    this.logPath = deps.logPath ?? process.env.GUARDED_GUARDIAN_LOG ?? null;
    this.now = deps.now ?? (() => Date.now());

    /** @type {number[]} timestamps (ms) de mutações recentes p/ anti-flapping. */
    this.mutationTimes = [];
    this.consecutiveBlocks = 0;
    this.breakerOpenUntil = 0;
  }

  get mode() {
    return this.cfg.mode === "enforce" ? "enforce" : "warn";
  }

  /**
   * Teto de conta resolvido (AC-6). Fail-safe: receita inválida/ausente → base.
   * @param {number|null|undefined} receitaAtribuida BRL (rolling, via CAPI/087)
   * @returns {number} teto diário BRL
   */
  resolveAccountCap(receitaAtribuida) {
    const base = this.cfg.base_daily_cap;
    if (typeof receitaAtribuida !== "number" || !Number.isFinite(receitaAtribuida) || receitaAtribuida < 0) {
      return base; // fail-safe: nunca acima do base sem sinal confiável
    }
    return base + this.cfg.reinvest_pct * receitaAtribuida;
  }

  /**
   * Interceptor síncrono (checks derivados de args + estado local).
   * @param {string} toolName
   * @param {Record<string, unknown>} args
   * @returns {null | { content: Array<object>, isError: true }}
   */
  check(toolName, args = {}) {
    if (!SPEND_TOOLS.has(toolName)) return null; // não gasta → guardian não opina

    const t = this.now();

    // Circuit-breaker aberto?
    if (this.breakerOpenUntil > t) {
      return this._verdict(toolName, args, {
        rule: "circuit_breaker_open",
        detail: `breaker aberto até ${new Date(this.breakerOpenUntil).toISOString()}`,
      });
    }

    // Teto por adset (AC-1): daily_budget vem em centavos.
    const capCentavos = this.cfg.max_daily_per_adset * 100;
    const budget = args.daily_budget;
    if (typeof budget === "number" && budget > capCentavos) {
      return this._verdict(toolName, args, {
        rule: "adset_daily_cap",
        detail: `daily_budget ${budget}c > teto ${capCentavos}c (R$${this.cfg.max_daily_per_adset})`,
      });
    }

    // Anti-flapping: registra e conta na janela de 1h.
    this.mutationTimes.push(t);
    const windowStart = t - 3600_000;
    this.mutationTimes = this.mutationTimes.filter((ts) => ts >= windowStart);
    if (this.mutationTimes.length > this.cfg.max_mutations_per_hour) {
      return this._verdict(toolName, args, {
        rule: "max_mutations_per_hour",
        detail: `${this.mutationTimes.length} mutações/1h > limite ${this.cfg.max_mutations_per_hour}`,
      });
    }

    // Nada violou → allow limpo (reseta contador de bloqueios).
    this.consecutiveBlocks = 0;
    this._log({ tool: toolName, verdict: "allow", would_block: false, rule: null });
    return null;
  }

  /** Materializa o veredito de uma regra violada conforme o modo (warn|enforce). */
  _verdict(toolName, args, { rule, detail }) {
    if (this.mode === "warn") {
      this._log({ tool: toolName, verdict: "allow", would_block: true, rule, detail });
      return null; // warn nunca bloqueia
    }
    // enforce
    this.consecutiveBlocks += 1;
    if (this.consecutiveBlocks >= this.cfg.circuit_breaker.consecutive_blocks_to_trip) {
      this.breakerOpenUntil = this.now() + this.cfg.circuit_breaker.cooldown_minutes * 60_000;
    }
    this._log({ tool: toolName, verdict: "block", would_block: true, rule, detail });
    return {
      content: [
        {
          type: "text",
          text:
            `🛡️ Guardian BLOQUEOU "${toolName}".\n` +
            `Regra: ${rule} — ${detail}.\n` +
            `Ação não foi enviada à Meta. Ajuste dentro dos limites ou peça aprovação humana.`,
        },
      ],
      isError: true,
    };
  }

  /** Append no decision log (JSONL). Falha de I/O nunca bloqueia. */
  _log(fields) {
    const record = { ts: new Date(this.now()).toISOString(), mode: this.mode, ...fields };
    if (fields.would_block) {
      this.logger?.warn?.(`[guardian] ${record.verdict} rule=${fields.rule} tool=${fields.tool}`);
    }
    if (!this.logPath) return;
    try {
      fs.appendFileSync(this.logPath, JSON.stringify(record) + "\n");
    } catch (err) {
      this.logger?.warn?.(`[guardian] falha ao escrever decision log: ${err?.message}`);
    }
  }
}
