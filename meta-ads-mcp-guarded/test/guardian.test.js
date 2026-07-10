import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { Guardian } from "../src/guardian.js";
import { loadConfig, DEFAULT_CONFIG } from "../src/config.js";

/** Config base com clock controlável. */
function makeGuardian(overrides = {}, deps = {}) {
  const config = { guardian: { ...DEFAULT_CONFIG.guardian, ...overrides } };
  return new Guardian(config, deps);
}

test("config: defaults seguros quando não há arquivo", () => {
  const cfg = loadConfig(undefined);
  assert.equal(cfg.guardian.mode, "warn");
  assert.equal(cfg.guardian.base_daily_cap, 300);
  assert.equal(cfg.guardian.max_daily_per_adset, 50);
});

test("config: lê o guardrails.yaml real do pacote caio-trafego", () => {
  const yamlPath = path.join(
    path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, "$1"),
    "..", "..", "caio-trafego", "hermes", "guardrails.yaml",
  );
  if (!fs.existsSync(yamlPath)) return; // roda de cópia local — tolera ausência
  const cfg = loadConfig(yamlPath);
  assert.equal(cfg.guardian.reinvest_pct, 0.2);
});

test("AC-6: teto de conta = base + pct×receita; fail-safe → base", () => {
  const g = makeGuardian();
  assert.equal(g.resolveAccountCap(1000), 300 + 0.2 * 1000); // 500
  assert.equal(g.resolveAccountCap(0), 300);
  assert.equal(g.resolveAccountCap(null), 300); // fail-safe
  assert.equal(g.resolveAccountCap(undefined), 300);
  assert.equal(g.resolveAccountCap(-50), 300); // nunca abaixo/estranho
  assert.equal(g.resolveAccountCap("lixo"), 300);
});

test("AC-1 warn: adset acima do teto NÃO bloqueia mas loga would_block", () => {
  const g = makeGuardian({ mode: "warn" });
  // teto R$50 = 5000c; propõe R$80 = 8000c
  const verdict = g.check("update_adset", { adset_id: "123", daily_budget: 8000 });
  assert.equal(verdict, null); // warn não bloqueia
});

test("AC-1 enforce: adset acima do teto BLOQUEIA", () => {
  const g = makeGuardian({ mode: "enforce" });
  const verdict = g.check("update_adset", { adset_id: "123", daily_budget: 8000 });
  assert.ok(verdict);
  assert.equal(verdict.isError, true);
  assert.match(verdict.content[0].text, /adset_daily_cap/);
});

test("adset dentro do teto passa", () => {
  const g = makeGuardian({ mode: "enforce" });
  assert.equal(g.check("update_adset", { adset_id: "123", daily_budget: 4000 }), null);
});

test("tool que não gasta não é avaliada pelo guardian", () => {
  const g = makeGuardian({ mode: "enforce" });
  assert.equal(g.check("get_insights", { adset_id: "123" }), null);
  assert.equal(g.check("update_ad", { ad_id: "123" }), null); // update_ad não está em SPEND_TOOLS
});

test("anti-flapping enforce: além do limite/hora bloqueia", () => {
  let clock = 1_000_000;
  const g = makeGuardian({ mode: "enforce", max_mutations_per_hour: 3 }, { now: () => clock });
  // 3 mutações válidas passam; a 4ª estoura a janela
  for (let i = 0; i < 3; i++) {
    clock += 1000;
    assert.equal(g.check("create_ad", { adset_id: "1" }), null);
  }
  clock += 1000;
  const verdict = g.check("create_ad", { adset_id: "1" });
  assert.ok(verdict);
  assert.match(verdict.content[0].text, /max_mutations_per_hour/);
});

test("circuit-breaker enforce: abre após N bloqueios e barra tudo no cooldown", () => {
  let clock = 5_000_000;
  const g = makeGuardian(
    { mode: "enforce", max_daily_per_adset: 10, circuit_breaker: { consecutive_blocks_to_trip: 3, cooldown_minutes: 30 } },
    { now: () => clock },
  );
  // 3 bloqueios seguidos (budget acima) → breaker abre
  for (let i = 0; i < 3; i++) {
    clock += 1000;
    assert.ok(g.check("update_adset", { adset_id: "1", daily_budget: 999999 }));
  }
  // agora até uma ação DENTRO do teto é barrada pelo breaker aberto
  clock += 1000;
  const verdict = g.check("update_adset", { adset_id: "1", daily_budget: 500 });
  assert.ok(verdict);
  assert.match(verdict.content[0].text, /circuit_breaker_open/);
  // após o cooldown, volta a permitir
  clock += 31 * 60_000;
  assert.equal(g.check("update_adset", { adset_id: "1", daily_budget: 500 }), null);
});

test("decision log JSONL registra toda decisão (allow limpo + would_block)", () => {
  const logPath = path.join(os.tmpdir(), `guardian-log-${Date.now()}.jsonl`);
  const g = makeGuardian({ mode: "warn" }, { logPath });
  g.check("update_adset", { adset_id: "1", daily_budget: 4000 }); // allow limpo
  g.check("update_adset", { adset_id: "1", daily_budget: 8000 }); // would_block
  const lines = fs.readFileSync(logPath, "utf8").trim().split("\n").map((l) => JSON.parse(l));
  assert.equal(lines.length, 2);
  assert.equal(lines[0].would_block, false);
  assert.equal(lines[1].would_block, true);
  assert.equal(lines[1].verdict, "allow"); // warn: loga would_block mas verdict=allow
  fs.unlinkSync(logPath);
});
