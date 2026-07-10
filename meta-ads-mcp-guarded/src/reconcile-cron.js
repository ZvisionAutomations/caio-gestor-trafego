#!/usr/bin/env node
/**
 * story-089 — entry do reconciler pra cron nativo do Hermes.
 * Uso (junto dos ciclos 08/14/20:30):  node src/reconcile-cron.js
 *
 * Conecta no meta-ads-mcp real (mesmo filho do proxy), lê get_insights, mapeia
 * cada adset → estado e escreve no caio_adset_state. Verificado na VPS.
 */
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import { createStateStore } from "./state_store.js";
import { runReconcile } from "./reconciler.js";

const logger = {
  info: (...m) => process.stderr.write(`[reconcile] ${m.join(" ")}\n`),
  warn: (...m) => process.stderr.write(`[reconcile][WARN] ${m.join(" ")}\n`),
};

function childSpawnConfig() {
  const command = process.env.GUARDED_CHILD_COMMAND || "npx";
  if (process.env.GUARDED_CHILD_ARGS_JSON) {
    try {
      const p = JSON.parse(process.env.GUARDED_CHILD_ARGS_JSON);
      if (Array.isArray(p)) return { command, args: p.map(String) };
    } catch {
      /* usa default */
    }
  }
  const args = process.env.GUARDED_CHILD_ARGS
    ? process.env.GUARDED_CHILD_ARGS.split(" ").filter(Boolean)
    : ["-y", "meta-ads-mcp"];
  return { command, args };
}

async function main() {
  const { command, args } = childSpawnConfig();
  const child = new Client({ name: "reconcile-cron", version: "0.1.0" }, { capabilities: {} });
  await child.connect(new StdioClientTransport({ command, args, env: process.env, stderr: "inherit" }));

  // O reconciler ESCREVE estado → usa a connection de escrita (role caio_rw).
  // Fallback pro CAIO_DATABASE_URL em dev; sem nenhuma → in-memory.
  const store = createStateStore({
    databaseUrl: process.env.CAIO_DB_WRITE_URL || process.env.CAIO_DATABASE_URL,
    logger,
  });
  const summary = await runReconcile(child, store, { logger });
  logger.info(`avaliados=${summary.evaluated} transições=${summary.transitioned}`);
  for (const c of summary.changes) logger.info(`  ${c.adset_id}: ${c.from ?? "∅"} → ${c.to}`);

  await child.close();
  process.exit(0);
}

main().catch((err) => {
  logger.warn(`falha: ${err?.stack || err}`);
  process.exit(1);
});
