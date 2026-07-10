/**
 * story-093 — Retargeting estruturado (lógica determinística, config-driven).
 *
 * Monta a **Campanha 2 (Retargeting, ABO)** com um **Adset C** cujo público é
 * "conversas iniciadas via Business Messaging nos últimos 14d que NÃO compraram"
 * — o público de maior intenção da conta. Segue o mesmo runtime de 090/092b: o
 * wrapper Node é a fonte do "o que fazer"; a execução chama de volta a pipeline
 * guardada do proxy (`callGuardedTool`), então cada mutante passa pelos
 * interceptors (091 schema, 088 Guardian, 094 compliance) — AC-5.
 *
 * NÃO parseia manifest via LLM (mesmo motivo da 092b): determinístico, sem
 * double-spend. Reusa o schema `CampaignManifest` (campaign+adset+ads) e o marker
 * de segmento no ad (`audience: retargeting`) — AC-3.
 *
 * Fonte única de números: os limites (14d, R$30-50/dia, ≥20% de diferenciação,
 * budget de entrada) vivem no config (`retargeting:` em guardrails.yaml); este
 * módulo só os consome.
 */
import { extractMetaId } from "./upload_inbox.js";

const VALID_FORMATS = new Set(["image", "video", "carousel"]);

function normalizeFormat(value) {
  const v = String(value ?? "").trim().toLowerCase();
  if (v === "static") return "image";
  return VALID_FORMATS.has(v) ? v : null;
}

/** Ad marcado como retargeting no manifest? (AC-3). Default = ToF (não retargeting). */
export function isRetargetingAd(ad) {
  const seg = String(ad?.audience ?? ad?.segment ?? "tof").trim().toLowerCase();
  return seg === "retargeting" || seg === "rtg" || ad?.retargeting === true;
}

/** AC-3 — só os criativos marcados retargeting entram na Campanha 2. */
export function filterRetargetingAds(manifest) {
  const ads = Array.isArray(manifest?.ads) ? manifest.ads : [];
  return ads.filter(isRetargetingAd);
}

// --------------------------------------------------------------------------- //
// Público (AC-1) — engajamento de mensagens 14d, excluindo compradores.
// --------------------------------------------------------------------------- //
/**
 * Especificação do custom audience de retargeting. Semântica (Business
 * Messaging): pessoas que iniciaram conversa com a página nos últimos N dias.
 * A exclusão de compradores acontece no adset (excluded_custom_audiences), não
 * aqui — para reusar uma audiência de compradores já existente quando houver.
 * @param {object} campaign manifest.campaign (page_id / whatsapp)
 * @param {object} cfg config.retargeting
 */
export function buildRetargetingAudience(campaign, cfg) {
  return {
    name: `Retargeting — conversas ${cfg.audience_retention_days}d — ${campaign.page_id}`,
    // subtype ENGAGEMENT sobre a página de mensagens (destino WhatsApp/Messenger).
    subtype: "ENGAGEMENT",
    engagement_source: cfg.engagement_source || "messaging",
    page_id: campaign.page_id,
    whatsapp_phone_number: campaign.whatsapp_phone_number,
    retention_days: cfg.audience_retention_days,
    // Semântica: quem enviou/iniciou conversa (não apenas viu). [NEEDS VERIFICATION assinatura Graph]
    inclusion_event: "messaging_conversation_started_7d",
  };
}

/** Mantém o budget do adset dentro da faixa de entrada de retargeting (AC-1). */
export function clampRetargetingBudget(dailyBudgetBrl, cfg) {
  const min = cfg.min_daily_budget_brl;
  const max = cfg.max_daily_budget_brl;
  const v = Number(dailyBudgetBrl);
  if (!Number.isFinite(v) || v <= 0) return min; // sem valor → piso da faixa
  return Math.min(max, Math.max(min, v));
}

// --------------------------------------------------------------------------- //
// Diferenciação / overlap (AC-4) — ≥20% de diferença entre adsets da campanha.
// --------------------------------------------------------------------------- //
/** Tokens comparáveis de um targeting (geo/idade/gênero/audiências in/ex). */
export function targetingSignature(targeting = {}) {
  const tokens = new Set();
  const geo = targeting.geo_locations?.countries || targeting.countries || targeting.locations;
  if (Array.isArray(geo)) geo.forEach((c) => tokens.add(`geo:${String(c).toUpperCase()}`));
  if (targeting.age_min != null || targeting.age_max != null) {
    tokens.add(`age:${targeting.age_min ?? "*"}-${targeting.age_max ?? "*"}`);
  }
  if (Array.isArray(targeting.genders) && targeting.genders.length) {
    tokens.add(`gender:${[...targeting.genders].sort().join(",")}`);
  }
  const inc = targeting.custom_audiences || targeting.custom_audiences_ids || [];
  (Array.isArray(inc) ? inc : []).forEach((a) => tokens.add(`ca:${idOf(a)}`));
  const exc = targeting.excluded_custom_audiences || targeting.excluded_custom_audiences_ids || [];
  (Array.isArray(exc) ? exc : []).forEach((a) => tokens.add(`xca:${idOf(a)}`));
  return tokens;
}

function idOf(a) {
  return String(a && typeof a === "object" ? a.id ?? a.audience_id ?? "" : a);
}

/** Diferenciação = 1 − Jaccard(A,B). 0 = idênticos, 1 = totalmente distintos. */
export function estimateDifferentiation(targetingA, targetingB) {
  const a = targetingSignature(targetingA);
  const b = targetingSignature(targetingB);
  if (a.size === 0 && b.size === 0) return 0;
  let inter = 0;
  for (const t of a) if (b.has(t)) inter += 1;
  const union = a.size + b.size - inter;
  if (union === 0) return 0;
  return 1 - inter / union;
}

/**
 * AC-4 — antes de lançar, cada par de adsets da MESMA campanha precisa de
 * diferenciação ≥ threshold. Retorna { ok, min_differentiation, pairs }.
 * @param {Array<{name?:string, targeting:object}>} adsets
 * @param {object} cfg config.retargeting
 */
export function checkOverlap(adsets, cfg) {
  const threshold = cfg.min_differentiation_pct;
  const list = Array.isArray(adsets) ? adsets : [];
  const pairs = [];
  let minDiff = 1;
  for (let i = 0; i < list.length; i += 1) {
    for (let j = i + 1; j < list.length; j += 1) {
      const differentiation = estimateDifferentiation(list[i].targeting, list[j].targeting);
      minDiff = Math.min(minDiff, differentiation);
      pairs.push({
        a: list[i].name ?? `adset_${i}`,
        b: list[j].name ?? `adset_${j}`,
        differentiation,
        ok: differentiation >= threshold,
      });
    }
  }
  return {
    ok: pairs.every((p) => p.ok),
    min_differentiation: list.length < 2 ? 1 : minDiff, // 0/1 adset → nada pra comparar
    threshold,
    pairs,
  };
}

// --------------------------------------------------------------------------- //
// Estrutura de conta ABO consolidada (AC-2) — documentável e aplicável.
// --------------------------------------------------------------------------- //
export function buildAccountStructure(cfg) {
  return {
    strategy: "ABO", // budget no adset (não CBO) — controle por segmento
    campaigns: [
      {
        role: "tof",
        name: "Campanha 1 — ToF (broad)",
        objective: "OUTCOME_ENGAGEMENT",
        adsets: [{ name: "Adset A — broad", audience: "broad" }],
      },
      {
        role: "retargeting",
        name: "Campanha 2 — Retargeting",
        objective: "OUTCOME_ENGAGEMENT",
        adsets: [
          {
            name: "Adset C — conversas sem compra",
            audience: `messaging_${cfg.audience_retention_days}d_no_purchase`,
            daily_budget_brl_range: [cfg.min_daily_budget_brl, cfg.max_daily_budget_brl],
          },
        ],
      },
    ],
    entry_budget_brl_range: [cfg.entry_budget_min_brl, cfg.entry_budget_max_brl],
  };
}

// --------------------------------------------------------------------------- //
// Cadeia de tool calls (AC-1/AC-5) — traduz o manifest de retargeting em passos.
// --------------------------------------------------------------------------- //
/**
 * @param {object} manifest CampaignManifest (com ads marcados retargeting)
 * @param {object} cfg config.retargeting
 * @returns {Array<{key,tool,idFrom,buildArgs}>} passos ordenados
 */
export function buildRetargetingSteps(manifest, cfg) {
  const c = manifest.campaign;
  const a = manifest.adset;
  const rtgAds = filterRetargetingAds(manifest);
  const steps = [];

  // Campanha 2 (ABO — sem budget de campanha; o budget vive no adset).
  steps.push({
    key: "campaign",
    tool: "create_campaign",
    idFrom: "id",
    buildArgs: () => ({
      name: c.retargeting_campaign_name || `${c.name} — Retargeting`,
      objective: "OUTCOME_ENGAGEMENT",
      status: "PAUSED",
      special_ad_categories: [],
      // ABO: sem daily_budget na campanha.
    }),
  });

  // Custom audience de conversas 14d.
  steps.push({
    key: "audience",
    tool: "create_custom_audience",
    idFrom: "id",
    buildArgs: () => buildRetargetingAudience(c, cfg),
  });

  // Adset C — inclui a audiência de conversas, exclui compradores (se houver).
  steps.push({
    key: "adset",
    tool: "create_adset",
    idFrom: "id",
    buildArgs: (ctx) => {
      const excluded = purchasersAudienceId(c, cfg);
      const targeting = {
        geo_locations: { countries: a?.locations || ["BR"] },
        custom_audiences: [ctx.audience],
        ...(excluded ? { excluded_custom_audiences: [excluded] } : {}),
      };
      return {
        campaign_id: ctx.campaign,
        name: a?.name ? `${a.name} — Retargeting` : "Adset C — Retargeting",
        daily_budget: Math.round(clampRetargetingBudget(a?.daily_budget_brl, cfg) * 100),
        billing_event: a?.billing_event || "IMPRESSIONS",
        optimization_goal: a?.optimization_goal || "CONVERSATIONS",
        destination_type: "WHATSAPP",
        status: "PAUSED",
        targeting,
        // AC-4 (destino de clique por-pacote, nunca global — mesmo princípio 092b).
        promoted_object: {
          page_id: c.page_id,
          whatsapp_phone_number: c.whatsapp_phone_number,
        },
      };
    },
  });

  // Só os criativos marcados retargeting (AC-3).
  rtgAds.forEach((ad, i) => {
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
        name: `${ad.name} — creative (rtg)`,
        page_id: c.page_id,
        whatsapp_phone_number: c.whatsapp_phone_number,
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
        name: `${ad.name} — rtg`,
        adset_id: ctx.adset,
        creative_id: ctx[`ad${i}_creative`],
        status: "PAUSED",
      }),
    });
  });

  return steps;
}

function purchasersAudienceId(campaign, cfg) {
  return (
    campaign?.purchasers_audience_id ||
    campaign?.exclude_purchasers_audience_id ||
    cfg?.purchasers_audience_id ||
    ""
  );
}

// --------------------------------------------------------------------------- //
// Orquestração (AC-1/AC-5) — roda a cadeia via callGuardedTool.
// --------------------------------------------------------------------------- //
/**
 * Cria/gerencia a Campanha 2 de retargeting a partir de um manifest já validado.
 * Pré-condições checadas: existe ≥1 criativo marcado retargeting (AC-3) e, se
 * `existingAdsets` for informado, a diferenciação passa no gate (AC-4).
 *
 * @param {object} p
 * @param {object} p.manifest CampaignManifest validado
 * @param {(name:string,args:object)=>Promise<any>} p.callGuardedTool pipeline guardada (AC-5)
 * @param {object} p.cfg config.retargeting
 * @param {Array<{name?:string,targeting:object}>} [p.existingAdsets] adsets já na campanha (p/ overlap)
 * @param {object} [p.ledger] idempotência opcional (mesmo contrato do upload_ledger)
 * @param {string} [p.manifestHash] chave de idempotência (se ledger informado)
 * @param {object} [p.logger]
 */
export async function runRetargeting({
  manifest,
  callGuardedTool,
  cfg,
  existingAdsets = null,
  ledger = null,
  manifestHash = "",
  logger,
}) {
  const rtgAds = filterRetargetingAds(manifest);
  if (rtgAds.length === 0) {
    return { status: "skipped", reason: "nenhum criativo marcado retargeting no manifest (AC-3)", created: 0 };
  }

  // AC-4 — gate de diferenciação antes de lançar (só se há adsets pra comparar).
  const adsetForOverlap = {
    name: "Adset C — Retargeting",
    targeting: { custom_audiences: ["__rtg_audience__"], geo_locations: { countries: manifest.adset?.locations || ["BR"] } },
  };
  const overlap = checkOverlap([...(existingAdsets || []), adsetForOverlap], cfg);
  if (!overlap.ok) {
    return {
      status: "blocked",
      reason: `overlap: diferenciação mínima ${(overlap.min_differentiation * 100).toFixed(0)}% < ${(overlap.threshold * 100).toFixed(0)}% (AC-4)`,
      overlap,
      created: 0,
    };
  }

  const steps = buildRetargetingSteps(manifest, cfg);
  const completed = ledger && manifestHash ? await ledger.getCompletedSteps(manifestHash) : {};
  const ctx = { ...completed };
  let resumed = 0;

  for (const step of steps) {
    if (completed[step.key]) {
      ctx[step.key] = completed[step.key];
      resumed += 1;
      continue;
    }
    const args = step.buildArgs(ctx);
    let result;
    try {
      result = await callGuardedTool(step.tool, args);
    } catch (err) {
      if (ledger && manifestHash) await ledger.recordStep(manifestHash, step.key, "", "error");
      return { status: "error", reason: `passo ${step.key} (${step.tool}) falhou: ${err?.message}`, overlap, resumed, created: 0 };
    }
    if (result?.isError) {
      if (ledger && manifestHash) await ledger.recordStep(manifestHash, step.key, "", "error");
      const txt = result?.content?.[0]?.text ?? "erro sem detalhe";
      return { status: "error", reason: `passo ${step.key} (${step.tool}) bloqueado/erro: ${txt}`, overlap, resumed, created: 0 };
    }
    const metaId = extractMetaId(result, step.idFrom);
    if (!metaId) {
      if (ledger && manifestHash) await ledger.recordStep(manifestHash, step.key, "", "error");
      return { status: "error", reason: `passo ${step.key} (${step.tool}) sem meta_id no retorno`, overlap, resumed, created: 0 };
    }
    ctx[step.key] = metaId;
    if (ledger && manifestHash) await ledger.recordStep(manifestHash, step.key, metaId, "done");
  }

  logger?.info?.(`[retargeting] Campanha 2 criada (${rtgAds.length} criativo(s) rtg, diff ${(overlap.min_differentiation * 100).toFixed(0)}%).`);
  return {
    status: resumed > 0 ? "resumed" : "created",
    campaign_id: ctx.campaign,
    adset_id: ctx.adset,
    audience_id: ctx.audience,
    ads: rtgAds.length,
    resumed,
    overlap,
    created: rtgAds.length,
  };
}
