/**
 * Teste de integração end-to-end do proxy, com o meta-ads-mcp substituído por
 * um filho mockado (test/mock-child.js). Verifica:
 *  - passthrough de tools/list (o proxy expõe as tools do filho)
 *  - passthrough de tool read-only (o filho roda)
 *  - passthrough de mutante VÁLIDA (o filho roda)
 *  - BLOQUEIO de mutante INVÁLIDA pela 091 (o filho NUNCA roda)
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const proxyEntry = path.join(here, "..", "src", "index.js");
const mockChild = path.join(here, "mock-child.js");

let client;
let transport;

before(async () => {
  // Sobe o PROXY apontando o filho pro mock (em vez de npx meta-ads-mcp).
  transport = new StdioClientTransport({
    command: process.execPath, // node
    args: [proxyEntry],
    env: {
      ...process.env,
      GUARDED_CHILD_COMMAND: process.execPath,
      GUARDED_CHILD_ARGS_JSON: JSON.stringify([mockChild]), // path com espaços → array exato
    },
    stderr: "inherit",
  });
  client = new Client({ name: "test-client", version: "0.0.1" }, { capabilities: {} });
  await client.connect(transport);
});

after(async () => {
  await client?.close();
});

test("tools/list faz passthrough das tools do filho", async () => {
  const { tools } = await client.listTools();
  const names = tools.map((t) => t.name);
  assert.ok(names.includes("get_campaigns"));
  assert.ok(names.includes("update_adset"));
});

test("read-only passa direto (filho roda)", async () => {
  const res = await client.callTool({ name: "get_campaigns", arguments: {} });
  assert.match(res.content[0].text, /CHILD_RAN:get_campaigns/);
  assert.notEqual(res.isError, true);
});

test("mutante VÁLIDA passa (filho roda)", async () => {
  const res = await client.callTool({
    name: "update_adset",
    arguments: { adset_id: "1201234567", daily_budget: 5000 },
  });
  assert.match(res.content[0].text, /CHILD_RAN:update_adset/);
  assert.notEqual(res.isError, true);
});

test("mutante INVÁLIDA é bloqueada pela 091 (filho NÃO roda)", async () => {
  const res = await client.callTool({
    name: "update_adset",
    arguments: { adset_id: "act_hallucinated" },
  });
  assert.equal(res.isError, true);
  assert.doesNotMatch(res.content[0].text, /CHILD_RAN/); // filho nunca foi chamado
  assert.match(res.content[0].text, /BLOQUEOU/);
});
