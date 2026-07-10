/**
 * story-093 — testes do retargeting estruturado.
 * Foco (QA da story): Campanha 2 ABO + Adset C (conversas 14d); consumo só dos
 * criativos marcados retargeting (AC-3); gate de diferenciação ≥20% (AC-4);
 * cadeia via callGuardedTool/Guardian (AC-5). Mock do MCP filho + ledger in-memory.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  isRetargetingAd,
  filterRetargetingAds,
  buildRetargetingAudience,
  clampRetargetingBudget,
  targetingSignature,
  estimateDifferentiation,
  checkOverlap,
  buildAccountStructure,
  buildRetargetingSteps,
  runRetargeting,
} from "../src/retargeting.js";
import { DEFAULT_CONFIG } from "../src/config.js";
import { InMemoryUploadLedger } from "../src/upload_ledger.js";

const RT = DEFAULT_CONFIG.retargeting;

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function manifest(overrides = {}) {
  return {
    campaign: {
      name: "AlphaPulse",
      product: "alpha-pulse",
      objective: "OUTCOME_ENGAGEMENT",
      status_on_upload: "paused",
      page_id: "PAGE_ALPHA",
      whatsapp_phone_number: "5511990000001",
      ...(overrides.campaign || {}),
    },
    adset: { name: "adset-1", daily_budget_brl: 40, locations: ["BR"], ...(overrides.adset || {}) },
    ads: overrides.ads || [
      { name: "rtg-1", format: "image", asset: "prova.jpg", primary_text: "t", headline: "h", audience: "retargeting" },
      { name: "tof-1", format: "image", asset: "broad.jpg", primary_text: "t", headline: "h" },
    ],
  };
}

function mockCaller(calls, { failOnCall = -1 } = {}) {
  let n = 0;
  return async (name, args) => {
    n += 1;
    calls.push({ name, args });
    if (n === failOnCall) throw new Error("boom (simulado)");
    return {
      content: [
        { type: "text", text: JSON.stringify({ id: `meta_${n}`, image_hash: `hash_${n}`, video_id: `vid_${n}` }) },
      ],
    };
  };
}

// --------------------------------------------------------------------------- //
// AC-3: marcação / filtro de criativos retargeting
// --------------------------------------------------------------------------- //
test("isRetargetingAd reconhece marcações e default ToF", () => {
  assert.equal(isRetargetingAd({ audience: "retargeting" }), true);
  assert.equal(isRetargetingAd({ segment: "rtg" }), true);
  assert.equal(isRetargetingAd({ retargeting: true }), true);
  assert.equal(isRetargetingAd({}), false);
  assert.equal(isRetargetingAd({ audience: "tof" }), false);
});

test("filterRetargetingAds pega só os marcados (AC-3)", () => {
  const ads = filterRetargetingAds(manifest());
  assert.equal(ads.length, 1);
  assert.equal(ads[0].name, "rtg-1");
});

// --------------------------------------------------------------------------- //
// AC-1: público + budget
// --------------------------------------------------------------------------- //
test("buildRetargetingAudience usa janela 14d e a página do pacote", () => {
  const aud = buildRetargetingAudience(manifest().campaign, RT);
  assert.equal(aud.retention_days, 14);
  assert.equal(aud.subtype, "ENGAGEMENT");
  assert.equal(aud.page_id, "PAGE_ALPHA");
});

test("clampRetargetingBudget mantém a faixa R$30-50", () => {
  assert.equal(clampRetargetingBudget(40, RT), 40);
  assert.equal(clampRetargetingBudget(10, RT), 30); // abaixo → piso
  assert.equal(clampRetargetingBudget(999, RT), 50); // acima → teto
  assert.equal(clampRetargetingBudget(0, RT), 30); // sem valor → piso
});

// --------------------------------------------------------------------------- //
// AC-4: diferenciação / overlap
// --------------------------------------------------------------------------- //
test("estimateDifferentiation: idênticos=0, distintos>0", () => {
  const broad = { geo_locations: { countries: ["BR"] } };
  const rtg = { geo_locations: { countries: ["BR"] }, custom_audiences: ["A1"] };
  assert.equal(estimateDifferentiation(broad, broad), 0);
  assert.ok(estimateDifferentiation(broad, rtg) > 0);
});

test("checkOverlap bloqueia adsets muito parecidos, passa os diferenciados (AC-4)", () => {
  const rtg = { name: "C", targeting: { geo_locations: { countries: ["BR"] }, custom_audiences: ["A1"] } };
  const clone = { name: "C2", targeting: { geo_locations: { countries: ["BR"] }, custom_audiences: ["A1"] } };
  const broad = { name: "A", targeting: { geo_locations: { countries: ["BR"] } } };
  assert.equal(checkOverlap([rtg, clone], RT).ok, false); // diff 0 < 20%
  assert.equal(checkOverlap([rtg, broad], RT).ok, true); // diff 50% ≥ 20%
  assert.equal(checkOverlap([rtg], RT).ok, true); // 1 adset → nada a comparar
});

// --------------------------------------------------------------------------- //
// AC-2: estrutura de conta ABO documentável
// --------------------------------------------------------------------------- //
test("buildAccountStructure descreve ABO: ToF + Retargeting + budget de entrada", () => {
  const s = buildAccountStructure(RT);
  assert.equal(s.strategy, "ABO");
  assert.deepEqual(s.campaigns.map((c) => c.role), ["tof", "retargeting"]);
  assert.deepEqual(s.entry_budget_brl_range, [130, 150]);
});

// --------------------------------------------------------------------------- //
// AC-1/AC-5: cadeia de passos
// --------------------------------------------------------------------------- //
test("buildRetargetingSteps: campanha → audiência → adset → só ad(s) rtg", () => {
  const steps = buildRetargetingSteps(manifest());
  assert.deepEqual(
    steps.map((s) => s.key),
    ["campaign", "audience", "adset", "ad0_asset", "ad0_creative", "ad0_ad"], // 1 ad rtg (o tof-1 fica fora)
  );
  assert.equal(steps[1].tool, "create_custom_audience");
});

test("buildRetargetingSteps: adset inclui a audiência e exclui compradores quando há", () => {
  const m = manifest({ campaign: { purchasers_audience_id: "BUYERS" } });
  const steps = buildRetargetingSteps(m, RT);
  const adsetStep = steps.find((s) => s.key === "adset");
  const args = adsetStep.buildArgs({ campaign: "c1", audience: "aud1" });
  assert.deepEqual(args.targeting.custom_audiences, ["aud1"]);
  assert.deepEqual(args.targeting.excluded_custom_audiences, ["BUYERS"]);
  assert.equal(args.daily_budget, 4000); // R$40 → centavos, dentro da faixa
});

// --------------------------------------------------------------------------- //
// AC-1/AC-5: orquestração via callGuardedTool
// --------------------------------------------------------------------------- //
test("runRetargeting sobe a Campanha 2 e passa cada mutante pela pipeline guardada", async () => {
  const calls = [];
  const res = await runRetargeting({
    manifest: manifest(),
    callGuardedTool: mockCaller(calls),
    cfg: RT,
    existingAdsets: [{ name: "A", targeting: { geo_locations: { countries: ["BR"] } } }], // ToF broad
  });
  assert.equal(res.status, "created");
  assert.equal(res.created, 1);
  assert.deepEqual(
    calls.map((c) => c.name),
    ["create_campaign", "create_custom_audience", "create_adset", "upload_ad_image", "create_ad_creative", "create_ad"],
  );
  // AC-5: todas em PAUSED
  const campaign = calls.find((c) => c.name === "create_campaign");
  assert.equal(campaign.args.status, "PAUSED");
});

test("runRetargeting pula quando não há criativo marcado retargeting (AC-3)", async () => {
  const calls = [];
  const res = await runRetargeting({
    manifest: manifest({ ads: [{ name: "tof", format: "image", asset: "a.jpg", primary_text: "t", headline: "h" }] }),
    callGuardedTool: mockCaller(calls),
    cfg: RT,
  });
  assert.equal(res.status, "skipped");
  assert.equal(calls.length, 0);
});

test("runRetargeting bloqueia lançamento com overlap insuficiente (AC-4)", async () => {
  const calls = [];
  // adset existente idêntico ao de retargeting (mesma audiência sintética + geo) → diff 0
  const clone = { name: "clone", targeting: { geo_locations: { countries: ["BR"] }, custom_audiences: ["__rtg_audience__"] } };
  const res = await runRetargeting({
    manifest: manifest(),
    callGuardedTool: mockCaller(calls),
    cfg: RT,
    existingAdsets: [clone],
  });
  assert.equal(res.status, "blocked");
  assert.equal(calls.length, 0); // não chamou a Graph
});

test("runRetargeting retoma do ledger sem re-chamar passos concluídos", async () => {
  const ledger = new InMemoryUploadLedger();
  const m = manifest();
  const hash = "rtg:test-hash";

  // 1ª execução falha na 3ª call (create_adset) → campaign+audience ficam 'done'.
  const calls1 = [];
  const res1 = await runRetargeting({
    manifest: m,
    callGuardedTool: mockCaller(calls1, { failOnCall: 3 }),
    cfg: RT,
    ledger,
    manifestHash: hash,
  });
  assert.equal(res1.status, "error");

  // 2ª execução: campaign+audience retomados do ledger (não re-chamados).
  const calls2 = [];
  const res2 = await runRetargeting({
    manifest: m,
    callGuardedTool: mockCaller(calls2),
    cfg: RT,
    ledger,
    manifestHash: hash,
  });
  assert.equal(res2.status, "resumed");
  assert.equal(res2.resumed, 2);
  assert.deepEqual(
    calls2.map((c) => c.name),
    ["create_adset", "upload_ad_image", "create_ad_creative", "create_ad"], // campaign+audience não re-chamados
  );
});
