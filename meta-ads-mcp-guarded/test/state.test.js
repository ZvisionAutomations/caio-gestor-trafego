import { test } from "node:test";
import assert from "node:assert/strict";

import { STATES, canTransition, canMutate, mapSignalToState } from "../src/state_machine.js";
import { InMemoryStateBackend } from "../src/state_store.js";
import { reconcile, defaultExtractSignals } from "../src/reconciler.js";
import { makeStateInterceptor } from "../src/interceptors.js";

test("transições válidas e inválidas", () => {
  assert.ok(canTransition("LEARNING", "ACTIVE"));
  assert.ok(canTransition("ACTIVE", "SCALING"));
  assert.ok(canTransition("FATIGUED", "PAUSED"));
  assert.ok(canTransition("ACTIVE", "ACTIVE")); // idempotente
  assert.equal(canTransition("LEARNING", "SCALING"), false); // não pula pra escala
  assert.equal(canTransition("PAUSED", "SCALING"), false);
});

test("canMutate: LEARNING bloqueia escala e edição de budget", () => {
  assert.equal(canMutate("LEARNING", "duplicate_ad_set", { adset_id: "1" }).allowed, false);
  assert.equal(canMutate("LEARNING", "update_adset", { adset_id: "1", daily_budget: 4000 }).allowed, false);
  assert.equal(canMutate("LEARNING", "pause_ad_set", { adset_id: "1" }).allowed, true); // pausar sempre pode
});

test("canMutate: FATIGUED bloqueia escala mas deixa pausar", () => {
  assert.equal(canMutate("FATIGUED", "duplicate_ad_set", { adset_id: "1" }).allowed, false);
  assert.equal(canMutate("FATIGUED", "pause_ad_set", { adset_id: "1" }).allowed, true);
});

test("canMutate: ACTIVE libera; estado desconhecido fail-open", () => {
  assert.equal(canMutate("ACTIVE", "duplicate_ad_set", { adset_id: "1" }).allowed, true);
  assert.equal(canMutate(null, "duplicate_ad_set", { adset_id: "1" }).allowed, true);
  assert.equal(canMutate("LIXO", "duplicate_ad_set", { adset_id: "1" }).allowed, true);
});

test("mapSignalToState (AC-2)", () => {
  assert.equal(mapSignalToState({ label: "FATIGUED" }), STATES.FATIGUED);
  assert.equal(mapSignalToState({ label: "CHAMPION", days_active: 10 }), STATES.SCALING);
  assert.equal(mapSignalToState({ label: "GOOD", days_active: 5 }), STATES.ACTIVE);
  assert.equal(mapSignalToState({ label: "INSUFFICIENT", days_active: 1 }), STATES.LEARNING);
  assert.equal(mapSignalToState({ days_active: 2 }), STATES.LEARNING); // <72h → learning
});

test("store in-memory: set/get + consecutive_ticks_in_state", async () => {
  const s = new InMemoryStateBackend();
  assert.equal(await s.getState("1"), null);
  await s.setState("1", "ACTIVE", { reason: "x" });
  assert.equal((await s.getState("1")).state, "ACTIVE");
  assert.equal((await s.getState("1")).consecutive_ticks_in_state, 0);
  // reconfirmar o mesmo estado incrementa o tick; entered_at preservado
  const entered = (await s.getState("1")).entered_at;
  await s.setState("1", "ACTIVE", { reason: "y" });
  assert.equal((await s.getState("1")).consecutive_ticks_in_state, 1);
  assert.equal((await s.getState("1")).entered_at, entered);
  // trocar de estado zera o tick
  await s.setState("1", "SCALING", { reason: "z" });
  assert.equal((await s.getState("1")).consecutive_ticks_in_state, 0);
});

test("reconcile escreve transições válidas e ignora inválidas", async () => {
  const store = new InMemoryStateBackend();
  await store.setState("10", "LEARNING");
  await store.setState("20", "SCALING");
  const signals = [
    { adset_id: "10", label: "GOOD", days_active: 5 }, // LEARNING→ACTIVE (válida)
    { adset_id: "20", label: "CHAMPION", days_active: 9 }, // SCALING→SCALING (sem mudança)
    { adset_id: "30", label: "INSUFFICIENT", days_active: 1 }, // novo → LEARNING
  ];
  const res = await reconcile(signals, store);
  assert.equal(res.transitioned, 2); // 10 e 30
  assert.equal((await store.getState("10")).state, "ACTIVE");
  assert.equal((await store.getState("30")).state, "LEARNING");
});

test("defaultExtractSignals parseia JSON do get_insights", () => {
  const result = { content: [{ type: "text", text: JSON.stringify({ data: [{ adset_id: "5", label: "GOOD", days_active: 4 }] }) }] };
  const sig = defaultExtractSignals(result);
  assert.equal(sig.length, 1);
  assert.equal(sig[0].adset_id, "5");
});

test("state interceptor enforce bloqueia escala em LEARNING", async () => {
  const store = new InMemoryStateBackend();
  await store.setState("7", "LEARNING");
  const interceptor = makeStateInterceptor(store, "enforce");
  const verdict = await interceptor("duplicate_ad_set", { adset_id: "7" }, {});
  assert.ok(verdict);
  assert.equal(verdict.isError, true);
});

test("state interceptor warn não bloqueia", async () => {
  const store = new InMemoryStateBackend();
  await store.setState("7", "LEARNING");
  const interceptor = makeStateInterceptor(store, "warn");
  const warns = [];
  const verdict = await interceptor("duplicate_ad_set", { adset_id: "7" }, { logger: { warn: (m) => warns.push(m) } });
  assert.equal(verdict, null);
  assert.equal(warns.length, 1);
});
