import { test } from "node:test";
import assert from "node:assert/strict";

import { Compliance, normalize, collectStrings } from "../src/compliance.js";
import { DEFAULT_CONFIG } from "../src/config.js";

function makeCompliance(overrides = {}, deps = {}) {
  const config = { compliance: { ...DEFAULT_CONFIG.compliance, ...overrides } };
  return new Compliance(config, deps);
}

test("normalize remove acento e caixa", () => {
  assert.equal(normalize("Menopáusa"), "menopausa");
  assert.equal(normalize("REPOSIÇÃO Hormonal"), "reposicao hormonal");
  assert.equal(normalize("Ansiedade"), "ansiedade");
});

test("collectStrings pega strings aninhadas (deep)", () => {
  const args = {
    name: "campanha x",
    targeting: { interests: ["menopausa", { label: "saude" }] },
    n: 42,
    ad: { primary_text: "texto", cards: [{ headline: "h1" }] },
  };
  const got = collectStrings(args);
  assert.ok(got.includes("menopausa"));
  assert.ok(got.includes("h1"));
  assert.ok(got.includes("texto"));
});

test("AC-2 enforce: copy com termo proibido (com acento) é bloqueada", () => {
  const c = makeCompliance({ mode: "enforce" });
  const verdict = c.check("create_ad", { primary_text: "Alívio da menopáusa em 7 dias" });
  assert.ok(verdict);
  assert.equal(verdict.isError, true);
  assert.match(verdict.content[0].text, /menopausa/);
});

test("AC-2 enforce: targeting por condição de saúde é bloqueado", () => {
  const c = makeCompliance({ mode: "enforce" });
  const verdict = c.check("create_adset", {
    adset_id: "1",
    targeting: { flexible_spec: [{ interests: [{ name: "Fertilidade" }] }] },
  });
  assert.ok(verdict);
  assert.match(verdict.content[0].text, /fertilidade/);
});

test("claim pattern 'antes e depois' é pego", () => {
  const c = makeCompliance({ mode: "enforce" });
  const verdict = c.check("create_ad_creative", { message: "Veja o antes e depois real!" });
  assert.ok(verdict);
});

test("copy limpa passa", () => {
  const c = makeCompliance({ mode: "enforce" });
  const verdict = c.check("create_ad", {
    primary_text: "Bem-estar diário para a mulher moderna. Naturalidade e energia.",
  });
  assert.equal(verdict, null);
});

test("AC-4 mas warn: match NÃO bloqueia (loga would_block)", () => {
  const c = makeCompliance({ mode: "warn" });
  const verdict = c.check("create_ad", { primary_text: "cura garantida da insônia" });
  assert.equal(verdict, null); // warn nunca bloqueia
});

test("tool sem conteúdo (read-only ou pause) não é avaliada", () => {
  const c = makeCompliance({ mode: "enforce" });
  assert.equal(c.check("get_insights", { primary_text: "menopausa" }), null);
  assert.equal(c.check("pause_ad_set", { adset_id: "1" }), null);
});

test("evita falso positivo por substring (curadoria ≠ cura)", () => {
  const c = makeCompliance({ mode: "enforce", prohibited_terms: ["cura"], claim_patterns: [] });
  // 'cura' casa por palavra (\b): 'curadoria' NÃO deve bater
  assert.equal(c.check("create_ad", { primary_text: "curadoria de produtos" }), null);
  // mas 'cura' como palavra bate
  assert.ok(c.check("create_ad", { primary_text: "cura definitiva" }));
});
