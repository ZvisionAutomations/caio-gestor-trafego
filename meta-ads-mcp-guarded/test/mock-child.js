#!/usr/bin/env node
/**
 * MCP filho MOCKADO para teste de integração do proxy.
 * Expõe 1 tool read-only (get_campaigns) e 1 mutante (update_adset).
 * update_adset ecoa os args — se o proxy repassar, o teste vê o eco;
 * se o proxy BLOQUEAR (091), o filho nunca é chamado e o eco não aparece.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "mock-meta-ads", version: "0.0.1" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    { name: "get_campaigns", description: "read-only", inputSchema: { type: "object" } },
    { name: "update_adset", description: "mutating", inputSchema: { type: "object" } },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args = {} } = req.params;
  return { content: [{ type: "text", text: `CHILD_RAN:${name}:${JSON.stringify(args)}` }] };
});

await server.connect(new StdioServerTransport());
