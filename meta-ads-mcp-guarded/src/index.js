#!/usr/bin/env node
/**
 * meta-ads-mcp-guarded — proxy MCP (artefato A do Caio v2).
 *
 * O Hermes aponta este server NO LUGAR do `meta-ads-mcp`. Internamente ele:
 *  1. Spawna o `meta-ads-mcp` real como processo filho (stdio).
 *  2. Faz passthrough de todas as tools (list + call).
 *  3. Nas tools MUTANTES, roda a pipeline de interceptors (091 hoje; 088/089/094
 *     depois) ANTES de repassar ao filho. Read-only passa direto.
 *
 * Zero divergência de upstream: o meta-ads-mcp continua sendo baixado via npx e
 * atualizável; só adicionamos a camada de guardrail à frente.
 *
 * IMPORTANTE: stdout é o canal JSON-RPC do MCP. TODO log vai pra stderr.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { buildPipeline, runPipeline } from "./interceptors.js";
import { loadConfig } from "./config.js";
import { Guardian } from "./guardian.js";
import { Compliance } from "./compliance.js";
import { createStateStore } from "./state_store.js";
import { createUploadLedger } from "./upload_ledger.js";
import { runUploadFromInbox, readManifest, scanInbox } from "./upload_inbox.js";
import { runRetargeting } from "./retargeting.js";

const NAME = "meta-ads-mcp-guarded";
const VERSION = "0.1.0";

const INBOX_DIR = process.env.CAIO_INBOX_DIR || "/opt/caio/inbox";

/** Tool NOVA (story-092b) — exposta pelo proxy além do passthrough do filho. */
const UPLOAD_TOOL = {
  name: "upload_creative_from_inbox",
  description:
    "Sobe pacotes de campanha de /opt/caio/inbox pro Meta em PAUSED, de forma determinística e idempotente (story-092b). Não parseia manifest via LLM.",
  inputSchema: {
    type: "object",
    properties: {
      campaign_folder: {
        type: "string",
        description: "Opcional. Nome de uma subpasta específica; default varre todas as não processadas.",
      },
    },
  },
};

/** Tool NOVA (story-093) — monta a Campanha 2 (Retargeting, ABO) a partir de um pacote. */
const RETARGETING_TOOL = {
  name: "build_retargeting_campaign",
  description:
    "Monta a Campanha 2 (Retargeting, ABO) — Adset C de conversas iniciadas sem compra (14d) — a partir de um pacote de /opt/caio/inbox, consumindo só os criativos marcados retargeting (story-093). Determinístico, em PAUSED, via guardrails.",
  inputSchema: {
    type: "object",
    properties: {
      campaign_folder: {
        type: "string",
        description: "Nome da subpasta do pacote (manifest.yaml) de onde tirar os criativos marcados retargeting.",
      },
    },
    required: ["campaign_folder"],
  },
};

const logger = {
  info: (...m) => process.stderr.write(`[guarded] ${m.join(" ")}\n`),
  warn: (...m) => process.stderr.write(`[guarded][WARN] ${m.join(" ")}\n`),
  error: (...m) => process.stderr.write(`[guarded][ERROR] ${m.join(" ")}\n`),
};

/** Comando/args do MCP filho — default meta-ads-mcp via npx; sobrescrevível p/ teste. */
function childSpawnConfig() {
  const command = process.env.GUARDED_CHILD_COMMAND || "npx";
  // GUARDED_CHILD_ARGS_JSON tem precedência (array exato — robusto a paths com espaço).
  // GUARDED_CHILD_ARGS é conveniência (split por espaço; ok pra "-y meta-ads-mcp").
  let args = ["-y", "meta-ads-mcp"];
  if (process.env.GUARDED_CHILD_ARGS_JSON) {
    try {
      const parsed = JSON.parse(process.env.GUARDED_CHILD_ARGS_JSON);
      if (Array.isArray(parsed)) args = parsed.map(String);
    } catch {
      logger.warn("GUARDED_CHILD_ARGS_JSON inválido (não é JSON array); usando default.");
    }
  } else if (process.env.GUARDED_CHILD_ARGS) {
    args = process.env.GUARDED_CHILD_ARGS.split(" ").filter(Boolean);
  }
  return { command, args };
}

async function main() {
  const { command, args } = childSpawnConfig();
  logger.info(`iniciando; filho = ${command} ${args.join(" ")}`);

  // 1. Conecta no meta-ads-mcp real (spawna o processo filho).
  const child = new Client({ name: `${NAME}-child`, version: VERSION }, { capabilities: {} });
  const childTransport = new StdioClientTransport({
    command,
    args,
    env: process.env, // repassa META_ACCESS_TOKEN / META_AD_ACCOUNT_ID etc.
    stderr: "inherit",
  });
  await child.connect(childTransport);
  logger.info("filho conectado.");

  // Guardrails config-driven (artefato C) + Guardian (088).
  const config = loadConfig(undefined, { logger });
  const guardian = new Guardian(config, { logger });
  const compliance = new Compliance(config, { logger });
  const stateStore = createStateStore({ logger }); // 089 — PG se CAIO_DATABASE_URL, senão in-memory
  const uploadLedger = createUploadLedger({ logger }); // 092b — idempotência multi-passo
  logger.info(
    `guardian=${guardian.mode} base_cap=R$${config.guardian.base_daily_cap} | compliance=${compliance.mode} (${config.compliance.prohibited_terms.length} termos) | state=${config.state.mode}`,
  );

  const pipeline = buildPipeline({
    guardian,
    compliance,
    stateStore,
    stateMode: config.state.mode,
    logger,
  });

  // 2. Expõe o server guardado pro Hermes.
  const server = new Server({ name: NAME, version: VERSION }, { capabilities: { tools: {} } });

  // tools/list → passthrough do filho + a tool nova do proxy (092b).
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const listed = await child.listTools();
    return { tools: [...listed.tools, UPLOAD_TOOL, RETARGETING_TOOL] };
  });

  // Chamada guardada: roda a pipeline (091/088/094) e só então repassa ao filho.
  // Reusada tanto pelo passthrough quanto pela cadeia de upload da 092b (AC-3).
  async function callGuardedTool(name, toolArgs = {}) {
    const blocked = await runPipeline(pipeline, name, toolArgs, { logger });
    if (blocked) {
      logger.warn(`tool "${name}" BLOQUEADA pela pipeline (não repassada ao filho).`);
      return blocked;
    }
    try {
      return await child.callTool({ name, arguments: toolArgs });
    } catch (err) {
      // Erro do filho/Graph API → devolve estruturado, não derruba o proxy.
      logger.error(`erro ao chamar "${name}" no filho: ${err?.message}`);
      return {
        content: [{ type: "text", text: `Erro ao executar "${name}": ${err?.message}` }],
        isError: true,
      };
    }
  }

  // tools/call → intercepta a tool 092b; senão, chamada guardada normal.
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: toolArgs = {} } = request.params;

    if (name === UPLOAD_TOOL.name) {
      try {
        const { summary, results } = await runUploadFromInbox({
          inboxDir: INBOX_DIR,
          campaignFolder: String(toolArgs.campaign_folder || ""),
          callGuardedTool,
          ledger: uploadLedger,
          logger,
        });
        const line = `inbox: subiu ${summary.subiu}, retomou ${summary.retomou}, pulou ${summary.pulou}, erro ${summary.erro} (de ${summary.total}).`;
        logger.info(`[inbox] ${line}`);
        return {
          content: [{ type: "text", text: `${line}\n${JSON.stringify(results, null, 2)}` }],
          isError: summary.erro > 0,
        };
      } catch (err) {
        logger.error(`[inbox] falha inesperada: ${err?.message}`);
        return {
          content: [{ type: "text", text: `Erro no upload_creative_from_inbox: ${err?.message}` }],
          isError: true,
        };
      }
    }

    if (name === RETARGETING_TOOL.name) {
      const folderName = String(toolArgs.campaign_folder || "");
      if (!folderName) {
        return { content: [{ type: "text", text: "campaign_folder é obrigatório." }], isError: true };
      }
      try {
        const [folder] = scanInbox(INBOX_DIR, { onlyFolder: folderName });
        // Aceita também pacotes já processados pelo upload (092b) — retargeting reusa os criativos.
        const target = folder || `${INBOX_DIR}/${folderName}`;
        const parsed = readManifest(target);
        if (!parsed.ok) {
          return { content: [{ type: "text", text: `Pacote "${folderName}": ${parsed.reason}` }], isError: true };
        }
        const result = await runRetargeting({
          manifest: parsed.manifest,
          callGuardedTool,
          cfg: config.retargeting,
          ledger: uploadLedger,
          manifestHash: `rtg:${parsed.hash}`,
          logger,
        });
        const line = `retargeting "${folderName}": ${result.status} (${result.created} criativo(s), diff ${(result.overlap?.min_differentiation ?? 1) * 100}%)${result.reason ? " — " + result.reason : ""}.`;
        logger.info(`[retargeting] ${line}`);
        return {
          content: [{ type: "text", text: `${line}\n${JSON.stringify(result, null, 2)}` }],
          isError: result.status === "error" || result.status === "blocked",
        };
      } catch (err) {
        logger.error(`[retargeting] falha inesperada: ${err?.message}`);
        return { content: [{ type: "text", text: `Erro no build_retargeting_campaign: ${err?.message}` }], isError: true };
      }
    }

    return callGuardedTool(name, toolArgs);
  });

  // Encerra limpo se o filho cair.
  childTransport.onclose = () => {
    logger.error("transporte do filho fechou — encerrando proxy.");
    process.exit(1);
  };

  await server.connect(new StdioServerTransport());
  logger.info("proxy pronto (stdio).");
}

main().catch((err) => {
  logger.error(`falha fatal no boot: ${err?.stack || err}`);
  process.exit(1);
});
