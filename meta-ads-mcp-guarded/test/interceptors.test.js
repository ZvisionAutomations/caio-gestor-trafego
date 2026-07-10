import { test } from "node:test";
import assert from "node:assert/strict";

import {
  schemaValidationInterceptor,
  buildPipeline,
  runPipeline,
} from "../src/interceptors.js";

test("schemaValidationInterceptor libera read-only", () => {
  assert.equal(schemaValidationInterceptor("get_campaigns", {}), null);
});

test("schemaValidationInterceptor libera mutante com args válidos", () => {
  assert.equal(schemaValidationInterceptor("update_adset", { adset_id: "123" }), null);
});

test("schemaValidationInterceptor bloqueia mutante com ID inválido", () => {
  const verdict = schemaValidationInterceptor("update_adset", { adset_id: "act_1" });
  assert.ok(verdict);
  assert.equal(verdict.isError, true);
});

test("runPipeline retorna primeiro bloqueio", async () => {
  const pipeline = buildPipeline();
  const verdict = await runPipeline(pipeline, "update_adset", { adset_id: "" }, {});
  assert.ok(verdict);
  assert.equal(verdict.isError, true);
});

test("runPipeline é fail-open: interceptor que lança não bloqueia", async () => {
  const boom = () => {
    throw new Error("bug no guardrail");
  };
  const warnings = [];
  const ctx = { logger: { warn: (m) => warnings.push(m) } };
  const verdict = await runPipeline([boom], "update_adset", { adset_id: "act_1" }, ctx);
  assert.equal(verdict, null); // exceção engolida → allow
  assert.equal(warnings.length, 1);
});
