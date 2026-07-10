/**
 * Story 089 — persistência do estado de adset (AC-3/AC-4/AC-5).
 *
 * Backend Postgres (`caio_adset_state`) quando `CAIO_DATABASE_URL` está setado;
 * senão cai pra in-memory por ciclo (AC-5, sem regressão) logando warning.
 *
 * O wrapper LÊ (getState); o reconciler ESCREVE (setState). PG verificado na VPS;
 * o backend in-memory é o coberto por teste aqui.
 */

/** Backend in-memory (fallback AC-5 + base de teste). */
export class InMemoryStateBackend {
  constructor() {
    this.map = new Map();
  }
  async getState(adsetId) {
    return this.map.get(String(adsetId)) ?? null;
  }
  async setState(adsetId, state, { reason = "", metadata = {} } = {}) {
    const id = String(adsetId);
    const prev = this.map.get(id);
    const sameState = prev && prev.state === state;
    // Espelha a semântica do Pg: reconfirmação do mesmo estado incrementa o tick,
    // troca de estado zera e reinicia entered_at.
    const ticks = sameState ? (prev.consecutive_ticks_in_state ?? 0) + 1 : 0;
    const now = new Date().toISOString();
    this.map.set(id, {
      adset_id: id,
      state,
      entered_at: sameState ? prev.entered_at : now,
      consecutive_ticks_in_state: ticks,
      metadata: { ...metadata, reason },
      updated_at: now,
    });
  }
}

/**
 * Backend Postgres. Thin — usa `pg`. Verificado na VPS (não há Postgres no dev local).
 * Import dinâmico do `pg` pra não exigir a dep quando roda in-memory.
 */
export class PgStateBackend {
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
  async getState(adsetId) {
    const pool = await this._poolRef();
    const { rows } = await pool.query(
      "SELECT adset_id, state, entered_at, consecutive_ticks_in_state, metadata FROM caio_adset_state WHERE adset_id = $1",
      [String(adsetId)],
    );
    return rows[0] ?? null;
  }
  async setState(adsetId, state, { reason = "", metadata = {} } = {}) {
    const pool = await this._poolRef();
    await pool.query(
      `INSERT INTO caio_adset_state (adset_id, state, entered_at, consecutive_ticks_in_state, metadata)
       VALUES ($1, $2, NOW(), 0, $3)
       ON CONFLICT (adset_id) DO UPDATE SET
         consecutive_ticks_in_state = CASE WHEN caio_adset_state.state = EXCLUDED.state
                                 THEN caio_adset_state.consecutive_ticks_in_state + 1 ELSE 0 END,
         state = EXCLUDED.state,
         entered_at = CASE WHEN caio_adset_state.state = EXCLUDED.state
                           THEN caio_adset_state.entered_at ELSE NOW() END,
         metadata = EXCLUDED.metadata,
         updated_at = NOW()`,
      [String(adsetId), state, JSON.stringify({ ...metadata, reason })],
    );
  }
}

/**
 * Fábrica: PG se houver CAIO_DATABASE_URL, senão in-memory (AC-5).
 * @param {{ databaseUrl?: string, logger?: object }} [opts]
 */
export function createStateStore(opts = {}) {
  const url = opts.databaseUrl ?? process.env.CAIO_DATABASE_URL;
  if (url) return new PgStateBackend(url);
  opts.logger?.warn?.("[state] CAIO_DATABASE_URL ausente — estado in-memory por ciclo (AC-5, sem persistência).");
  return new InMemoryStateBackend();
}
