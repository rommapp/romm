import Database from "better-sqlite3";
import { resolve } from "path";

const dbPath = resolve("./data/oidc_data.sqlite");
const db = new Database(dbPath);

// Initialize the database schema
db.exec(`
  CREATE TABLE IF NOT EXISTS oidc (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    expiresAt INTEGER
  )
`);

class SQLiteAdapter {
  constructor(name) {
    this.name = name;
  }

  async upsert(id, payload, expiresIn) {
    const expiresAt = expiresIn ? Date.now() + expiresIn * 1000 : null;
    const stmt = db.prepare(`
      INSERT INTO oidc (id, name, payload, expiresAt)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        payload=excluded.payload,
        expiresAt=excluded.expiresAt
    `);
    stmt.run(id, this.name, JSON.stringify(payload), expiresAt);
  }

  async find(id) {
    const stmt = db.prepare(`SELECT * FROM oidc WHERE id = ? AND name = ?`);
    const record = stmt.get(id, this.name);
    if (!record) return undefined;
    if (record.expiresAt && record.expiresAt < Date.now()) {
      await this.destroy(id);
      return undefined;
    }
    return JSON.parse(record.payload);
  }

  async destroy(id) {
    const stmt = db.prepare(`DELETE FROM oidc WHERE id = ? AND name = ?`);
    stmt.run(id, this.name);
  }

  async revokeByGrantId(grantId) {
    const stmt = db.prepare(
      `DELETE FROM oidc WHERE json_extract(payload, '$.grantId') = ? AND name = ?`,
    );
    stmt.run(grantId, this.name);
  }
}

export default SQLiteAdapter;
