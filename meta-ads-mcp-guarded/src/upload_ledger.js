/**
 * story-092b — ledger transacional do upload multi-passo (`caio_upload_ledger`).
 *
 * Keyed por (manifest_hash, step_key). Cada sub-passo grava seu `meta_id` ANTES
 * de avançar; o re-run consulta os passos `done` e retoma reusando os IDs — nunca
 * duplica creative (furo C do slicing). Backend Postgres quando `CAIO_DATABASE_URL`
 * está setado; senão in-memory por ciclo (base de teste + fallback sem regressão),
 * espelhando o padrão do `state_store.js` (089).
 */

/** Backend in-memory (fallback + base de teste). */
export class InMemoryUploadLedger {
  constructor() {
    this.map = new Map(); // `${hash}::${step}` -> { meta_id, status }
  }
  _k(hash, step) {
    return `${hash}::${step}`;
  }
  async getCompletedSteps(manifestHash) {
    const out = {};
    for (const [k, v] of this.map.entries()) {
      const [hash, step] = k.split("::");
      if (hash === manifestHash && v.status === "done" && v.meta_id) out[step] = v.meta_id;
    }
    return out;
  }
  async recordStep(manifestHash, stepKey, metaId, status) {
    this.map.set(this._k(manifestHash, stepKey), { meta_id: metaId || "", status });
  }
}

/** Backend Postgres. Import dinâmico do `pg` (não exige a dep no modo in-memory). */
export class PgUploadLedger {
  constructor(connectionString) {
    this.connectionString = connectionString.replace("+asyncpg", "");
    this._pool = null;
  }
  async _poolRef() {
    if (this._pool) return this._pool;
    const { default: pg } = await import("pg");
    this._pool = new pg.Pool({ connectionString: this.connectionString, max: 2 });
    return this._pool;
  }
  async getCompletedSteps(manifestHash) {
    const pool = await this._poolRef();
    const { rows } = await pool.query(
      "SELECT step_key, meta_id FROM caio_upload_ledger WHERE manifest_hash = $1 AND status = 'done' AND meta_id <> ''",
      [manifestHash],
    );
    const out = {};
    for (const r of rows) out[r.step_key] = r.meta_id;
    return out;
  }
  async recordStep(manifestHash, stepKey, metaId, status) {
    const pool = await this._poolRef();
    await pool.query(
      `INSERT INTO caio_upload_ledger (manifest_hash, step_key, meta_id, status, created_at, updated_at)
       VALUES ($1, $2, $3, $4, NOW(), NOW())
       ON CONFLICT (manifest_hash, step_key) DO UPDATE SET
         meta_id = EXCLUDED.meta_id,
         status = EXCLUDED.status,
         updated_at = NOW()`,
      [manifestHash, stepKey, metaId || "", status],
    );
  }
}

/** Fábrica: PG se houver CAIO_DATABASE_URL, senão in-memory. */
export function createUploadLedger(opts = {}) {
  const url = opts.databaseUrl ?? process.env.CAIO_DATABASE_URL;
  if (url) return new PgUploadLedger(url);
  opts.logger?.warn?.(
    "[ledger] CAIO_DATABASE_URL ausente — upload ledger in-memory por ciclo (sem persistência entre runs).",
  );
  return new InMemoryUploadLedger();
}
