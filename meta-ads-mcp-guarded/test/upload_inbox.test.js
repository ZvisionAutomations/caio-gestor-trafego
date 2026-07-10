/**
 * story-092b — testes da tool `upload_creative_from_inbox`.
 * Foco (QA da story): multi-passo com falha no meio NÃO duplica creative
 * (ledger retoma); manifest inválido não derruba os outros; roteamento
 * por-campanha (AC-4) sem hardcode. MCP filho mockado + ledger in-memory.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  validateManifest,
  manifestHash,
  scanInbox,
  buildSteps,
  extractMetaId,
  uploadPackage,
  runUploadFromInbox,
  PROCESSED_MARKER,
} from "../src/upload_inbox.js";
import { InMemoryUploadLedger } from "../src/upload_ledger.js";

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function validManifestObj(overrides = {}) {
  return {
    campaign: {
      name: "AlphaPulse Aquisição",
      product: "alpha-pulse",
      objective: "OUTCOME_ENGAGEMENT",
      status_on_upload: "paused",
      page_id: "PAGE_ALPHA",
      whatsapp_phone_number: "5511990000001",
      ...(overrides.campaign || {}),
    },
    adset: {
      name: "adset-1",
      daily_budget_brl: 50,
      locations: ["BR"],
      ...(overrides.adset || {}),
    },
    ads: overrides.ads || [
      {
        name: "ad-1",
        format: "image",
        asset: "creative.jpg",
        primary_text: "texto",
        headline: "titulo",
      },
    ],
  };
}

function yamlFor(obj) {
  // Serialização mínima suficiente pro parser (usa a lib yaml via JSON->YAML? não —
  // gravamos YAML de verdade). Usamos JSON, que é subconjunto válido de YAML.
  return JSON.stringify(obj, null, 2);
}

function makePackage(dir, name, manifestObj, { withMarker = false } = {}) {
  const folder = path.join(dir, name);
  fs.mkdirSync(folder, { recursive: true });
  fs.writeFileSync(path.join(folder, "manifest.yaml"), yamlFor(manifestObj));
  fs.writeFileSync(path.join(folder, "creative.jpg"), "fake-bytes");
  if (withMarker) fs.writeFileSync(path.join(folder, PROCESSED_MARKER), "{}");
  return folder;
}

function tmpInbox() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "caio-inbox-"));
}

/** Mock callGuardedTool: registra chamadas e devolve ids sintéticos. */
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
// AC-2: validação
// --------------------------------------------------------------------------- //
test("validateManifest aceita manifest válido", () => {
  const { ok, issues } = validateManifest(validManifestObj());
  assert.equal(ok, true, issues.join("; "));
});

test("validateManifest rejeita page_id ausente (AC-4)", () => {
  const { ok, issues } = validateManifest(validManifestObj({ campaign: { page_id: "" } }));
  assert.equal(ok, false);
  assert.ok(issues.some((i) => i.includes("page_id")));
});

test("validateManifest rejeita ads vazio e carrossel com 1 card", () => {
  assert.equal(validateManifest(validManifestObj({ ads: [] })).ok, false);
  const carousel = validManifestObj({
    ads: [{ name: "c", format: "carousel", primary_text: "t", headline: "h", cards: [{ asset: "a.jpg" }] }],
  });
  assert.equal(validateManifest(carousel).ok, false);
});

// --------------------------------------------------------------------------- //
// AC-5: hash muda com assets
// --------------------------------------------------------------------------- //
test("manifestHash é estável e sensível a assets", () => {
  const m = validManifestObj();
  assert.equal(manifestHash(m, ["a:1"]), manifestHash(m, ["a:1"]));
  assert.notEqual(manifestHash(m, ["a:1"]), manifestHash(m, ["a:2"]));
});

// --------------------------------------------------------------------------- //
// AC-1: scan ignora processados
// --------------------------------------------------------------------------- //
test("scanInbox ignora pastas com .caio_processed", () => {
  const inbox = tmpInbox();
  makePackage(inbox, "pendente", validManifestObj());
  makePackage(inbox, "ja-feita", validManifestObj(), { withMarker: true });
  const found = scanInbox(inbox).map((f) => path.basename(f));
  assert.deepEqual(found, ["pendente"]);
});

// --------------------------------------------------------------------------- //
// AC-3/AC-6: happy path — cadeia completa + commit do marker
// --------------------------------------------------------------------------- //
test("uploadPackage sobe a cadeia e escreve o marker só no fim", async () => {
  const inbox = tmpInbox();
  const folder = makePackage(inbox, "pkg", validManifestObj());
  const calls = [];
  const res = await uploadPackage({
    folder,
    callGuardedTool: mockCaller(calls),
    ledger: new InMemoryUploadLedger(),
  });

  assert.equal(res.status, "uploaded");
  assert.deepEqual(
    calls.map((c) => c.name),
    ["create_campaign", "create_adset", "upload_ad_image", "create_ad_creative", "create_ad"],
  );
  assert.ok(fs.existsSync(path.join(folder, PROCESSED_MARKER)), "marker deve existir no commit");
});

// --------------------------------------------------------------------------- //
// AC-2: manifest inválido não sobe nada e não escreve marker
// --------------------------------------------------------------------------- //
test("uploadPackage pula manifest inválido sem chamar a Graph", async () => {
  const inbox = tmpInbox();
  const folder = makePackage(inbox, "ruim", validManifestObj({ campaign: { page_id: "" } }));
  const calls = [];
  const res = await uploadPackage({
    folder,
    callGuardedTool: mockCaller(calls),
    ledger: new InMemoryUploadLedger(),
  });

  assert.equal(res.status, "skipped");
  assert.equal(calls.length, 0);
  assert.equal(fs.existsSync(path.join(folder, PROCESSED_MARKER)), false);
});

// --------------------------------------------------------------------------- //
// AC-5: falha no meio + re-run retoma sem duplicar
// --------------------------------------------------------------------------- //
test("uploadPackage retoma do passo pendente reusando ids (não duplica)", async () => {
  const inbox = tmpInbox();
  const folder = makePackage(inbox, "pkg", validManifestObj());
  const ledger = new InMemoryUploadLedger();

  // 1ª execução falha na 3ª chamada (upload_ad_image) -> campaign+adset ficam 'done'.
  const calls1 = [];
  const res1 = await uploadPackage({ folder, callGuardedTool: mockCaller(calls1, { failOnCall: 3 }), ledger });
  assert.equal(res1.status, "error");
  assert.equal(fs.existsSync(path.join(folder, PROCESSED_MARKER)), false);

  // 2ª execução: os 2 primeiros passos são retomados do ledger (não re-chamados).
  const calls2 = [];
  const res2 = await uploadPackage({ folder, callGuardedTool: mockCaller(calls2), ledger });
  assert.equal(res2.status, "resumed");
  assert.equal(res2.resumed, 2);
  assert.deepEqual(
    calls2.map((c) => c.name),
    ["upload_ad_image", "create_ad_creative", "create_ad"], // campaign+adset NÃO re-chamados
  );
  assert.ok(fs.existsSync(path.join(folder, PROCESSED_MARKER)));
});

// --------------------------------------------------------------------------- //
// AC-4: roteamento multi-produto — cada pacote usa seu page_id/whatsapp
// --------------------------------------------------------------------------- //
test("runUploadFromInbox roteia page_id/whatsapp por pacote (sem global)", async () => {
  const inbox = tmpInbox();
  makePackage(inbox, "alpha", validManifestObj({ campaign: { page_id: "PAGE_ALPHA", whatsapp_phone_number: "5511000000001" } }));
  makePackage(
    inbox,
    "newwoman",
    validManifestObj({ campaign: { name: "New Woman", product: "new-woman", page_id: "PAGE_NW", whatsapp_phone_number: "5511000000002" } }),
  );

  const calls = [];
  const { summary } = await runUploadFromInbox({
    inboxDir: inbox,
    callGuardedTool: mockCaller(calls),
    ledger: new InMemoryUploadLedger(),
  });

  assert.equal(summary.subiu, 2);
  const creatives = calls.filter((c) => c.name === "create_ad_creative");
  const pages = creatives.map((c) => c.args.page_id).sort();
  assert.deepEqual(pages, ["PAGE_ALPHA", "PAGE_NW"]);
  // cada creative casa page_id com o whatsapp do MESMO pacote
  for (const c of creatives) {
    if (c.args.page_id === "PAGE_ALPHA") assert.equal(c.args.whatsapp_phone_number, "5511000000001");
    if (c.args.page_id === "PAGE_NW") assert.equal(c.args.whatsapp_phone_number, "5511000000002");
  }
});

// --------------------------------------------------------------------------- //
// AC-2: um pacote inválido não derruba os outros
// --------------------------------------------------------------------------- //
test("runUploadFromInbox: pacote inválido é pulado, válidos sobem", async () => {
  const inbox = tmpInbox();
  makePackage(inbox, "ok", validManifestObj());
  makePackage(inbox, "quebrado", validManifestObj({ adset: { daily_budget_brl: 0 } }));

  const { summary } = await runUploadFromInbox({
    inboxDir: inbox,
    callGuardedTool: mockCaller([]),
    ledger: new InMemoryUploadLedger(),
  });

  assert.equal(summary.subiu, 1);
  assert.equal(summary.pulou, 1);
});

// --------------------------------------------------------------------------- //
// utilidades
// --------------------------------------------------------------------------- //
test("buildSteps gera a ordem correta por ad", () => {
  const steps = buildSteps(validManifestObj());
  assert.deepEqual(
    steps.map((s) => s.key),
    ["campaign", "adset", "ad0_asset", "ad0_creative", "ad0_ad"],
  );
});

test("extractMetaId lê id de JSON e via regex de fallback", () => {
  assert.equal(extractMetaId({ content: [{ type: "text", text: '{"id":"abc123"}' }] }), "abc123");
  assert.equal(extractMetaId({ content: [{ type: "text", text: "created id=xyz789 ok" }] }), "xyz789");
  assert.equal(
    extractMetaId({ content: [{ type: "text", text: '{"image_hash":"h1"}' }] }, "image_hash"),
    "h1",
  );
});
