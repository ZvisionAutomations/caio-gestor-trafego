/**
 * story-092b — Tool MCP `upload_creative_from_inbox`.
 *
 * Pega os pacotes de campanha que o rclone (092a) deposita em `/opt/caio/inbox/`
 * e sobe pro Meta em PAUSED, de forma DETERMINÍSTICA e IDEMPOTENTE — sem o LLM
 * parsear manifest (risco de alucinação/double-spend) e sem subir o mesmo
 * criativo duas vezes.
 *
 * Idempotência (AC-5/AC-6): cada sub-passo (create_campaign → create_adset →
 * per-ad upload_ad_image → create_ad_creative → create_ad) grava seu `meta_id`
 * no ledger `caio_upload_ledger`, keyed por (hash do manifest+assets, step). Se
 * a execução cair no meio, o re-run RETOMA do passo pendente reusando os IDs já
 * criados. O marker `.caio_processed` (commit) só é escrito quando a cadeia
 * inteira do pacote fecha.
 *
 * A cadeia de upload chama de volta a MESMA pipeline guardada do proxy
 * (`callGuardedTool`), então cada mutante passa pelos interceptors 091/088/094
 * (AC-3). Multi-produto (AC-4): cada ad usa `page_id`/`whatsapp_phone_number` do
 * manifest DAQUELE pacote — nunca um valor global.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { parse as parseYaml } from "yaml";

export const PROCESSED_MARKER = ".caio_processed";
const MANIFEST_FILE = "manifest.yaml";

const VALID_OBJECTIVES = new Set(["OUTCOME_ENGAGEMENT", "OUTCOME_SALES"]);
const VALID_FORMATS = new Set(["image", "video", "carousel"]);

// --------------------------------------------------------------------------- //
// Manifest validation (AC-2) — espelho enxuto do CampaignManifest (pydantic).
// NÃO redefine o schema: valida os campos que a cadeia de upload consome.
// --------------------------------------------------------------------------- //
/** @returns {{ ok: boolean, manifest?: object, issues: string[] }} */
export function validateManifest(raw) {
  const issues = [];
  if (!raw || typeof raw !== "object") {
    return { ok: false, issues: ["manifest vazio ou não é um mapa YAML"] };
  }

  const campaign = raw.campaign;
  const adset = raw.adset;
  const ads = raw.ads;

  // campaign
  if (!campaign || typeof campaign !== "object") {
    issues.push("campaign ausente");
  } else {
    if (!campaign.name) issues.push("campaign.name ausente");
    if (!campaign.product) issues.push("campaign.product ausente");
    if (!campaign.page_id) issues.push("campaign.page_id ausente (AC-4: destino de clique)");
    if (!campaign.whatsapp_phone_number)
      issues.push("campaign.whatsapp_phone_number ausente (AC-4: destino de clique)");
    const objective = normalizeObjective(campaign.objective);
    if (!objective) issues.push("campaign.objective inválido (OUTCOME_ENGAGEMENT|OUTCOME_SALES)");
    const statusOk = String(campaign.status_on_upload ?? "paused").toLowerCase() === "paused";
    if (!statusOk) issues.push("campaign.status_on_upload deve ser paused");
  }

  // adset
  if (!adset || typeof adset !== "object") {
    issues.push("adset ausente");
  } else {
    if (!adset.name) issues.push("adset.name ausente");
    const budget = Number(adset.daily_budget_brl);
    if (!(budget > 0)) issues.push("adset.daily_budget_brl deve ser > 0");
    const hasTargeting =
      (adset.targeting && typeof adset.targeting === "object") ||
      (Array.isArray(adset.locations) && adset.locations.length > 0);
    if (!hasTargeting) issues.push("adset.targeting ou adset.locations é obrigatório");
  }

  // ads
  if (!Array.isArray(ads) || ads.length < 1) {
    issues.push("ads deve ter ao menos 1 item");
  } else {
    ads.forEach((ad, i) => {
      const fmt = normalizeFormat(ad?.format);
      if (!fmt) {
        issues.push(`ads[${i}].format inválido (image|video|static|carousel)`);
        return;
      }
      if (!ad.name) issues.push(`ads[${i}].name ausente`);
      if (!ad.primary_text) issues.push(`ads[${i}].primary_text ausente`);
      if (!ad.headline) issues.push(`ads[${i}].headline ausente`);
      if (fmt === "carousel") {
        if (!Array.isArray(ad.cards) || ad.cards.length < 2)
          issues.push(`ads[${i}] carrossel exige >= 2 cards`);
        else
          ad.cards.forEach((c, j) => {
            if (!c?.asset) issues.push(`ads[${i}].cards[${j}].asset ausente`);
          });
      } else if (!ad.asset) {
        issues.push(`ads[${i}] (${fmt}) exige 'asset'`);
      }
    });
  }

  if (issues.length) return { ok: false, issues };
  return { ok: true, manifest: raw, issues: [] };
}

function normalizeObjective(value) {
  const v = String(value ?? "OUTCOME_ENGAGEMENT").trim().toUpperCase();
  if (v === "MESSAGES") return "OUTCOME_ENGAGEMENT";
  return VALID_OBJECTIVES.has(v) ? v : null;
}

function normalizeFormat(value) {
  const v = String(value ?? "").trim().toLowerCase();
  if (v === "static") return "image";
  return VALID_FORMATS.has(v) ? v : null;
}

// --------------------------------------------------------------------------- //
// Fingerprint / hash (AC-5) — hash do manifest + assets do pacote.
// --------------------------------------------------------------------------- //
/** Lista (nome, tamanho) dos arquivos do pacote (exceto marker) — determinístico. */
export function fingerprintAssets(folder) {
  let entries = [];
  try {
    entries = fs
      .readdirSync(folder, { withFileTypes: true })
      .filter((d) => d.isFile() && d.name !== PROCESSED_MARKER)
      .map((d) => {
        let size = 0;
        try {
          size = fs.statSync(path.join(folder, d.name)).size;
        } catch {
          /* best-effort */
        }
        return `${d.name}:${size}`;
      })
      .sort();
  } catch {
    /* best-effort */
  }
  return entries;
}

export function manifestHash(rawManifest, assetFingerprints) {
  const payload = JSON.stringify({
    manifest: rawManifest ?? null,
    assets: assetFingerprints ?? [],
  });
  return crypto.createHash("sha256").update(payload).digest("hex");
}

// --------------------------------------------------------------------------- //
// Scan (AC-1) — subpastas sem o marker `.caio_processed`.
// --------------------------------------------------------------------------- //
export function scanInbox(inboxDir, { onlyFolder = "" } = {}) {
  let dirs = [];
  try {
    dirs = fs
      .readdirSync(inboxDir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name);
  } catch {
    return [];
  }
  if (onlyFolder) dirs = dirs.filter((name) => name === onlyFolder);
  return dirs
    .map((name) => path.join(inboxDir, name))
    .filter((folder) => !fs.existsSync(path.join(folder, PROCESSED_MARKER)));
}

// --------------------------------------------------------------------------- //
// Step builder — traduz o manifest na cadeia ordenada de tool calls.
// Espelha campaign_inbox.py::translate(). Arg-shapes marcados p/ verificação
// de integração na VPS (assinatura real do meta-ads-mcp).
// --------------------------------------------------------------------------- //
export function buildSteps(manifest) {
  const c = manifest.campaign;
  const a = manifest.adset;
  const steps = [];

  steps.push({
    key: "campaign",
    tool: "create_campaign",
    idFrom: "id",
    buildArgs: () => ({
      name: c.name,
      objective: normalizeObjective(c.objective),
      status: "PAUSED",
      special_ad_categories: [],
    }),
  });

  steps.push({
    key: "adset",
    tool: "create_adset",
    idFrom: "id",
    buildArgs: (ctx) => ({
      campaign_id: ctx.campaign,
      name: a.name,
      daily_budget: Math.round(Number(a.daily_budget_brl) * 100),
      billing_event: a.billing_event || "IMPRESSIONS",
      optimization_goal: a.optimization_goal || "CONVERSATIONS",
      destination_type: "WHATSAPP",
      status: "PAUSED",
      // AC-4: destino de clique por-pacote, nunca global.
      promoted_object: {
        page_id: c.page_id,
        whatsapp_phone_number: c.whatsapp_phone_number,
      },
    }),
  });

  manifest.ads.forEach((ad, i) => {
    const fmt = normalizeFormat(ad.format);
    const assetTool = fmt === "video" ? "upload_ad_video" : "upload_ad_image";
    const assetIdField = fmt === "video" ? "video_id" : "image_hash";

    steps.push({
      key: `ad${i}_asset`,
      tool: assetTool,
      idFrom: assetIdField,
      buildArgs: () => ({ file: ad.asset }),
    });

    steps.push({
      key: `ad${i}_creative`,
      tool: "create_ad_creative",
      idFrom: "id",
      buildArgs: (ctx) => ({
        name: `${ad.name} — creative`,
        page_id: c.page_id, // AC-4
        whatsapp_phone_number: c.whatsapp_phone_number, // AC-4
        primary_text: ad.primary_text,
        headline: ad.headline,
        cta: ad.cta || "SEND_MESSAGE",
        [assetIdField]: ctx[`ad${i}_asset`],
      }),
    });

    steps.push({
      key: `ad${i}_ad`,
      tool: "create_ad",
      idFrom: "id",
      buildArgs: (ctx) => ({
        name: ad.name,
        adset_id: ctx.adset,
        creative_id: ctx[`ad${i}_creative`],
        status: "PAUSED",
      }),
    });
  });

  return steps;
}

/** Extrai o meta_id do resultado de uma tool call (best-effort, formato do meta-ads-mcp). */
export function extractMetaId(result, idField = "id") {
  const text = result?.content?.[0]?.text ?? "";
  if (text) {
    try {
      const parsed = JSON.parse(text);
      const val = parsed?.[idField] ?? parsed?.id ?? parsed?.image_hash ?? parsed?.video_id;
      if (val) return String(val);
    } catch {
      const m = text.match(/"?(?:id|image_hash|video_id)"?\s*[:=]\s*"?([\w:-]+)"?/i);
      if (m) return m[1];
    }
  }
  return "";
}

// --------------------------------------------------------------------------- //
// Upload de um pacote com resume (AC-3/AC-5/AC-6).
// --------------------------------------------------------------------------- //
export async function uploadPackage({ folder, callGuardedTool, ledger, logger }) {
  const manifestPath = path.join(folder, MANIFEST_FILE);
  const name = path.basename(folder);

  let raw;
  try {
    raw = parseYaml(fs.readFileSync(manifestPath, "utf8"));
  } catch (err) {
    return { folder: name, status: "skipped", reason: `manifest ilegível: ${err?.message}` };
  }

  const check = validateManifest(raw);
  if (!check.ok) {
    // AC-2: pula o pacote, reporta o motivo, NÃO sobe nada.
    return { folder: name, status: "skipped", reason: `manifest inválido: ${check.issues.join("; ")}` };
  }

  const hash = manifestHash(raw, fingerprintAssets(folder));
  const completed = await ledger.getCompletedSteps(hash); // { stepKey: metaId }
  const steps = buildSteps(check.manifest);

  const ctx = { ...completed };
  let resumed = 0;
  for (const step of steps) {
    if (completed[step.key]) {
      ctx[step.key] = completed[step.key];
      resumed += 1;
      continue; // AC-5: retoma reusando o ID já criado, sem re-chamar a Graph.
    }
    const args = step.buildArgs(ctx);
    let result;
    try {
      result = await callGuardedTool(step.tool, args);
    } catch (err) {
      await ledger.recordStep(hash, step.key, "", "error");
      return { folder: name, status: "error", reason: `passo ${step.key} (${step.tool}) falhou: ${err?.message}`, resumed };
    }
    if (result?.isError) {
      await ledger.recordStep(hash, step.key, "", "error");
      const txt = result?.content?.[0]?.text ?? "erro sem detalhe";
      return { folder: name, status: "error", reason: `passo ${step.key} (${step.tool}) bloqueado/erro: ${txt}`, resumed };
    }
    const metaId = extractMetaId(result, step.idFrom);
    if (!metaId) {
      await ledger.recordStep(hash, step.key, "", "error");
      return { folder: name, status: "error", reason: `passo ${step.key} (${step.tool}) sem meta_id no retorno`, resumed };
    }
    ctx[step.key] = metaId;
    await ledger.recordStep(hash, step.key, metaId, "done");
  }

  // AC-6: só agora escreve o marker (commit da "transação").
  try {
    fs.writeFileSync(
      path.join(folder, PROCESSED_MARKER),
      JSON.stringify({ manifest_hash: hash, processed_at: new Date().toISOString() }, null, 2),
    );
  } catch (err) {
    logger?.warn?.(`[inbox] pacote ${name} subiu mas falhou ao gravar marker: ${err?.message}`);
  }

  return { folder: name, status: resumed > 0 ? "resumed" : "uploaded", resumed, steps: steps.length };
}

/**
 * Lê + valida o manifest de um pacote e calcula o hash de idempotência.
 * Reusado pela 092b (upload) e pela 093 (retargeting) — mesma fonte de verdade.
 * @returns {{ ok: boolean, manifest?: object, hash?: string, reason?: string, issues?: string[] }}
 */
export function readManifest(folder) {
  const manifestPath = path.join(folder, MANIFEST_FILE);
  let raw;
  try {
    raw = parseYaml(fs.readFileSync(manifestPath, "utf8"));
  } catch (err) {
    return { ok: false, reason: `manifest ilegível: ${err?.message}` };
  }
  const check = validateManifest(raw);
  if (!check.ok) {
    return { ok: false, reason: `manifest inválido: ${check.issues.join("; ")}`, issues: check.issues };
  }
  const hash = manifestHash(raw, fingerprintAssets(folder));
  return { ok: true, manifest: check.manifest, hash };
}

// --------------------------------------------------------------------------- //
// Orquestração da tool (AC-1/AC-7).
// --------------------------------------------------------------------------- //
export async function runUploadFromInbox({ inboxDir, campaignFolder = "", callGuardedTool, ledger, logger }) {
  const folders = scanInbox(inboxDir, { onlyFolder: campaignFolder });
  const results = [];
  for (const folder of folders) {
    // eslint-disable-next-line no-await-in-loop
    results.push(await uploadPackage({ folder, callGuardedTool, ledger, logger }));
  }

  const summary = {
    subiu: results.filter((r) => r.status === "uploaded").length,
    retomou: results.filter((r) => r.status === "resumed").length,
    pulou: results.filter((r) => r.status === "skipped").length,
    erro: results.filter((r) => r.status === "error").length,
    total: results.length,
  };
  return { summary, results };
}
