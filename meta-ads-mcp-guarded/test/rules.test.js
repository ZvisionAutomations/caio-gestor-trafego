import { test } from "node:test";
import assert from "node:assert/strict";

import { evaluateAdset, reinvestBudget } from "../src/rules.js";
import { DEFAULT_CONFIG } from "../src/config.js";

const R = DEFAULT_CONFIG.rules;

test("AC-2 pausa composta: só com TODAS as condições", () => {
  const base = { cpl_proxy_brl: 30, freq: 4, hours_running: 100, spend_brl: 80 };
  assert.equal(evaluateAdset(base, "ACTIVE", R).action, "pause");
  // tira uma condição → não pausa (não age por métrica única)
  assert.notEqual(evaluateAdset({ ...base, freq: 2 }, "ACTIVE", R).action, "pause");
  assert.notEqual(evaluateAdset({ ...base, hours_running: 10 }, "ACTIVE", R).action, "pause");
  assert.notEqual(evaluateAdset({ ...base, spend_brl: 20 }, "ACTIVE", R).action, "pause");
});

test("AC-5 kill: gasto alto sem conversão", () => {
  const d = evaluateAdset({ spend_brl: 150, conversions: 0, days_running: 5 }, "ACTIVE", R);
  assert.equal(d.action, "kill");
});

test("AC-5 kill: idade máxima sem conversão", () => {
  const d = evaluateAdset({ spend_brl: 30, conversions: 0, days_running: 15 }, "ACTIVE", R);
  assert.equal(d.action, "kill");
});

test("AC-5 fadiga: freq alta + CTR caindo >20%", () => {
  const d = evaluateAdset({ freq: 4, ctr_prev: 2.0, ctr_now: 1.4, spend_brl: 40, conversions: 3 }, "ACTIVE", R);
  assert.equal(d.action, "fatigue_variant");
});

test("AC-3 escala: CPL baixo, >72h sem edição, fora do learning", () => {
  const m = { cpl_purchase_brl: 25, hours_since_edit: 100, days_profitable_consecutive: 3, conversions: 5 };
  const d = evaluateAdset(m, "ACTIVE", R); // 25 < 0.8*40=32 → lucrativo
  assert.ok(d.action === "scale" || d.action === "duplicate");
  assert.equal(d.autonomous, false); // só 3d lucrativo (<7) → pede aprovação
});

test("AC-3.1 autonomia: escala autônoma só com ≥7d lucrativo fora do learning", () => {
  const m = { cpl_purchase_brl: 25, hours_since_edit: 100, days_profitable_consecutive: 8, conversions: 5 };
  const d = evaluateAdset(m, "ACTIVE", R);
  assert.equal(d.autonomous, true);
});

test("AC-3 salto grande (>2×) → duplicar em vez de editar", () => {
  const m = { cpl_purchase_brl: 15, hours_since_edit: 100, days_profitable_consecutive: 8, conversions: 9 };
  // 15 < 40/2=20 → bigJump → duplicate
  assert.equal(evaluateAdset(m, "SCALING", R).action, "duplicate");
});

test("AC-4/089: não escala em LEARNING", () => {
  const m = { cpl_purchase_brl: 25, hours_since_edit: 100, days_profitable_consecutive: 8, conversions: 5 };
  const d = evaluateAdset(m, "LEARNING", R);
  assert.equal(d.action, "hold"); // learning não escala
});

test("hold quando nada satisfaz", () => {
  assert.equal(evaluateAdset({ cpl_proxy_brl: 15, freq: 2, spend_brl: 30, conversions: 1 }, "ACTIVE", R).action, "hold");
});

test("AC-3.2 reinvestimento: novo budget = base + 20% da receita; sem receita → base", () => {
  assert.equal(reinvestBudget(100, 500, R), 100 + 0.2 * 500); // 200
  assert.equal(reinvestBudget(100, 0, R), 100);
  assert.equal(reinvestBudget(100, null, R), 100); // fail-safe
});
