use rusqlite::{Connection, Result, params};
use serde_json;
use crate::types::{Identity, Asset, Trustline};

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new(path: &str) -> Result<Self> {
        let conn = Connection::open(path)?;
        Self::init_tables(&conn)?;
        Ok(Self { conn })
    }

    fn init_tables(conn: &Connection) -> Result<()> {
        // Tabella identities (esistente)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS identities (
                id TEXT PRIMARY KEY,
                name TEXT,
                mnemonic TEXT,
                master_public_key TEXT,
                fingerprint TEXT UNIQUE,
                created_at TEXT
            )",
            [],
        )?;

        // Tabella wallets (esistente)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS wallets (
                id TEXT PRIMARY KEY,
                identity_id TEXT,
                network TEXT,
                address TEXT,
                asset_code TEXT,
                asset_issuer TEXT,
                FOREIGN KEY (identity_id) REFERENCES identities(id)
            )",
            [],
        )?;

        // Tabella gateway_cache (esistente)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS gateway_cache (
                id TEXT PRIMARY KEY,
                rns_address TEXT UNIQUE,
                ledger_address TEXT,
                network TEXT,
                assets TEXT, -- JSON
                last_seen TEXT
            )",
            [],
        )?;

        // 🔥 NUOVA TABELLA: trustlines
        conn.execute(
            "CREATE TABLE IF NOT EXISTS trustlines (
                id TEXT PRIMARY KEY,
                identity_id TEXT NOT NULL,
                network TEXT NOT NULL,
                asset_code TEXT NOT NULL,
                asset_issuer TEXT,
                asset_decimals INTEGER NOT NULL,
                limit_amount REAL,
                balance REAL,
                authorized INTEGER NOT NULL DEFAULT 0,
                peer_authorized INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (identity_id) REFERENCES identities(id)
            )",
            [],
        )?;

        // 🔥 INDICE per ricerche veloci
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trustlines_identity ON trustlines(identity_id)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trustlines_asset ON trustlines(network, asset_code, asset_issuer)",
            [],
        )?;

        Ok(())
    }

    // ============================================================
    // IDENTITY - OPERAZIONI (esistenti)
    // ============================================================

    pub fn save_identity(&self, identity: &Identity) -> Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO identities 
             (id, name, mnemonic, master_public_key, fingerprint, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                identity.id,
                identity.name,
                identity.mnemonic,
                identity.master_public_key,
                identity.fingerprint,
                identity.created_at.to_rfc3339()
            ],
        )?;
        Ok(())
    }

    pub fn get_identity(&self, id: &str) -> Result<Option<Identity>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, name, mnemonic, master_public_key, fingerprint, created_at 
             FROM identities WHERE id = ?1"
        )?;
        
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(Identity {
                id: row.get(0)?,
                name: row.get(1)?,
                mnemonic: row.get(2)?,
                master_public_key: row.get(3)?,
                fingerprint: row.get(4)?,
                created_at: chrono::DateTime::parse_from_rfc3339(&row.get::<_, String>(5)?)
                    .unwrap()
                    .with_timezone(&chrono::Utc),
            }))
        } else {
            Ok(None)
        }
    }

    // ============================================================
    // TRUSTLINE - OPERAZIONI (NUOVE)
    // ============================================================

    // --- SAVE ---

    pub fn save_trustline(&self, trustline: &Trustline) -> Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO trustlines (
                id, identity_id, network, asset_code, asset_issuer, asset_decimals,
                limit_amount, balance, authorized, peer_authorized,
                created_at, updated_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
            params![
                trustline.id,
                trustline.identity_id,
                trustline.asset.network.to_string(),
                trustline.asset.code,
                trustline.asset.issuer,
                trustline.asset.decimals,
                trustline.limit,
                trustline.balance,
                trustline.authorized as i32,
                trustline.peer_authorized as i32,
                trustline.created_at.timestamp(),
                trustline.updated_at.timestamp(),
            ],
        )?;
        Ok(())
    }

    // --- GET BY ID ---

    pub fn get_trustline(&self, id: &str) -> Result<Option<Trustline>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, identity_id, network, asset_code, asset_issuer, asset_decimals,
                    limit_amount, balance, authorized, peer_authorized,
                    created_at, updated_at
             FROM trustlines WHERE id = ?1"
        )?;
        
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(self._row_to_trustline(row)?))
        } else {
            Ok(None)
        }
    }

    // --- GET BY IDENTITY ---

    pub fn get_trustlines_by_identity(&self, identity_id: &str) -> Result<Vec<Trustline>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, identity_id, network, asset_code, asset_issuer, asset_decimals,
                    limit_amount, balance, authorized, peer_authorized,
                    created_at, updated_at
             FROM trustlines WHERE identity_id = ?1 ORDER BY created_at DESC"
        )?;
        
        let mut rows = stmt.query(params![identity_id])?;
        let mut trustlines = Vec::new();
        
        while let Some(row) = rows.next()? {
            trustlines.push(self._row_to_trustline(row)?);
        }
        
        Ok(trustlines)
    }

    // --- GET BY ASSET ---

    pub fn get_trustline_by_asset(
        &self, 
        identity_id: &str, 
        network: &str, 
        asset_code: &str, 
        issuer: &Option<String>
    ) -> Result<Option<Trustline>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, identity_id, network, asset_code, asset_issuer, asset_decimals,
                    limit_amount, balance, authorized, peer_authorized,
                    created_at, updated_at
             FROM trustlines 
             WHERE identity_id = ?1 AND network = ?2 AND asset_code = ?3 AND asset_issuer = ?4"
        )?;
        
        let mut rows = stmt.query(params![identity_id, network, asset_code, issuer])?;
        if let Some(row) = rows.next()? {
            Ok(Some(self._row_to_trustline(row)?))
        } else {
            Ok(None)
        }
    }

    // --- CHECK EXISTS ---

    pub fn has_trustline(&self, identity_id: &str, network: &str, asset_code: &str, issuer: &Option<String>) -> Result<bool> {
        let mut stmt = self.conn.prepare(
            "SELECT COUNT(*) FROM trustlines 
             WHERE identity_id = ?1 AND network = ?2 AND asset_code = ?3 AND asset_issuer = ?4"
        )?;
        
        let count: i64 = stmt.query_row(
            params![identity_id, network, asset_code, issuer],
            |row| row.get(0)
        )?;
        
        Ok(count > 0)
    }

    // --- DELETE ---

    pub fn delete_trustline(&self, id: &str) -> Result<()> {
        self.conn.execute(
            "DELETE FROM trustlines WHERE id = ?1",
            params![id],
        )?;
        Ok(())
    }

    // --- DELETE BY IDENTITY AND ASSET ---

    pub fn delete_trustline_by_asset(
        &self, 
        identity_id: &str, 
        network: &str, 
        asset_code: &str, 
        issuer: &Option<String>
    ) -> Result<()> {
        self.conn.execute(
            "DELETE FROM trustlines 
             WHERE identity_id = ?1 AND network = ?2 AND asset_code = ?3 AND asset_issuer = ?4",
            params![identity_id, network, asset_code, issuer],
        )?;
        Ok(())
    }

    // --- UPDATE BALANCE ---

    pub fn update_trustline_balance(&self, id: &str, balance: f64) -> Result<()> {
        self.conn.execute(
            "UPDATE trustlines SET balance = ?1, updated_at = ?2 WHERE id = ?3",
            params![balance, chrono::Utc::now().timestamp(), id],
        )?;
        Ok(())
    }

    // --- UPDATE LIMIT ---

    pub fn update_trustline_limit(&self, id: &str, limit: f64) -> Result<()> {
        self.conn.execute(
            "UPDATE trustlines SET limit_amount = ?1, updated_at = ?2 WHERE id = ?3",
            params![limit, chrono::Utc::now().timestamp(), id],
        )?;
        Ok(())
    }

    // --- UPDATE AUTHORIZED ---

    pub fn update_trustline_authorized(&self, id: &str, authorized: bool, peer_authorized: bool) -> Result<()> {
        self.conn.execute(
            "UPDATE trustlines SET authorized = ?1, peer_authorized = ?2, updated_at = ?3 WHERE id = ?4",
            params![authorized as i32, peer_authorized as i32, chrono::Utc::now().timestamp(), id],
        )?;
        Ok(())
    }

    // --- HELPER: row to Trustline ---

    fn _row_to_trustline(&self, row: &rusqlite::Row) -> Result<Trustline> {
        use crate::types::asset::Network;
        
        let network_str: String = row.get(2)?;
        let network = match network_str.as_str() {
            "XRPL" => Network::XRPL,
            "Stellar" => Network::Stellar,
            "Bitcoin" => Network::Bitcoin,
            "Ethereum" => Network::Ethereum,
            "Monero" => Network::Monero,
            _ => Network::XRPL,
        };

        Ok(Trustline {
            id: row.get(0)?,
            identity_id: row.get(1)?,
            asset: Asset {
                network,
                issuer: row.get(4)?,
                code: row.get(3)?,
                decimals: row.get(5)?,
            },
            limit: row.get(6)?,
            balance: row.get(7)?,
            authorized: row.get::<_, i32>(8)? != 0,
            peer_authorized: row.get::<_, i32>(9)? != 0,
            created_at: chrono::DateTime::from_timestamp(row.get(10)?, 0).unwrap_or(chrono::Utc::now()),
            updated_at: chrono::DateTime::from_timestamp(row.get(11)?, 0).unwrap_or(chrono::Utc::now()),
        })
    }
}