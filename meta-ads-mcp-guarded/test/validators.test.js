import { test } from "node:test";
import assert from "node:assert/strict";

import {
  isMutatingTool,
  validateToolArgs,
  buildValidationErrorResult,
  META_NUMERIC_ID,
} from "../src/validators.js";

test("isMutatingTool distingue mutante de read-only", () => {
  assert.equal(isMutatingTool("update_adset"), true);
  assert.equal(isMutatingTool("create_ad"), true);
  assert.equal(isMutatingTool("pause_ad_set"), true); // alias legado
  assert.equal(isMutatingTool("get_campaigns"), false);
  assert.equal(isMutatingTool("get_insights"), false);
  assert.equal(isMutatingTool("search_ads"), false);
});

test("regex de ID Meta aceita numérico puro e rejeita prefixos", () => {
  assert.match("120210000000", META_NUMERIC_ID);
  assert.doesNotMatch("act_608013046286862", META_NUMERIC_ID);
  assert.doesNotMatch("adset_123", META_NUMERIC_ID);
  assert.doesNotMatch("", META_NUMERIC_ID);
  assert.doesNotMatch("12a3", META_NUMERIC_ID);
});

test("AC-2: adset_id numérico válido passa", () => {
  const r = validateToolArgs("update_adset", { adset_id: "1201234567", daily_budget: 5000 });
  assert.deepEqual(r, { ok: true });
});

test("AC-2: adset_id com prefixo act_/lixo é rejeitado (ID alucinado)", () => {
  const r = validateToolArgs("update_adset", { adset_id: "adset_ABC" });
  assert.equal(r.ok, false);
  assert.equal(r.issues[0].field, "adset_id");
});

test("AC-1: campo obrigatório ausente é rejeitado", () => {
  const r = validateToolArgs("update_adset", { daily_budget: 5000 });
  assert.equal(r.ok, false);
  assert.ok(r.issues.some((i) => i.field === "adset_id"));
});

test("AC-5: extra=allow — campos extras não conhecidos não quebram", () => {
  const r = validateToolArgs("update_adset", {
    adset_id: "1201234567",
    campo_maluco: "qualquer coisa",
    outro: 42,
  });
  assert.deepEqual(r, { ok: true });
});

test("valida IDs numéricos onde aparecerem, mesmo não-obrigatórios", () => {
  // create_ad exige adset_id; campaign_id (se presente) também precisa ser numérico.
  const r = validateToolArgs("create_ad", { adset_id: "123", campaign_id: "act_999" });
  assert.equal(r.ok, false);
  assert.ok(r.issues.some((i) => i.field === "campaign_id"));
});

test("tool read-only nunca é validada (passthrough)", () => {
  const r = validateToolArgs("get_campaigns", { account_id: "act_608013046286862" });
  assert.deepEqual(r, { ok: true });
});

test("buildValidationErrorResult produz MCP tool result com isError", () => {
  const res = buildValidationErrorResult("update_adset", [
    { field: "adset_id", expected: "numérico", got: "adset_x" },
  ]);
  assert.equal(res.isError, true);
  assert.equal(res.content[0].type, "text");
  assert.match(res.content[0].text, /update_adset/);
  assert.match(res.content[0].text, /adset_id/);
});
