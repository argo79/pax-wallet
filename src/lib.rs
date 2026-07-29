// ============================================================
// IMPORTS
// ============================================================
use serde::{Deserialize, Serialize};
use ed25519_dalek::SigningKey;
use bip39::{Mnemonic, Language};
use sha2::{Sha256, Digest};
use rusqlite::{Connection, Result as SqlResult, params};
use chrono::{DateTime, Utc};
use std::fmt;
use rand::Rng;

// ============================================================
// NETWORKING (sempre presente)
// ============================================================
use reqwest;

// ============================================================
// PYTHON FFI (opzionale)
// ============================================================
#[cfg(feature = "python")]
use pyo3::prelude::*;

// ============================================================
// NETWORK
// ============================================================
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Network {
    XRPL,
    Stellar,
    Bitcoin,
    Ethereum,
    Monero,
}

impl fmt::Display for Network {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

// ============================================================
// ASSET
// ============================================================
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Asset {
    pub network: Network,
    pub issuer: Option<String>,
    pub code: String,
    pub decimals: u8,
}

impl fmt::Display for Asset {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(issuer) = &self.issuer {
            write!(f, "{}.{}@{}", self.code, issuer, self.network)
        } else {
            write!(f, "{}.{}", self.code, self.network)
        }
    }
}

impl Asset {
    pub fn new(network: Network, code: &str, decimals: u8) -> Self {
        Self {
            network,
            issuer: None,
            code: code.to_string(),
            decimals,
        }
    }

    pub fn with_issuer(mut self, issuer: &str) -> Self {
        self.issuer = Some(issuer.to_string());
        self
    }

    pub fn xrp() -> Self {
        Self::new(Network::XRPL, "XRP", 6)
    }

    pub fn xlm() -> Self {
        Self::new(Network::Stellar, "XLM", 7)
    }

    pub fn rlusd() -> Self {
        Self::new(Network::XRPL, "RLUSD", 6)
            .with_issuer("rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth")
    }
}

// ============================================================
// TRUSTLINE - NUOVO
// ============================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trustline {
    pub id: String,
    pub identity_id: String,
    pub asset: Asset,
    pub limit: Option<f64>,
    pub balance: Option<f64>,
    pub authorized: bool,
    pub peer_authorized: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Trustline {
    pub fn new(identity_id: &str, asset: Asset, limit: Option<f64>) -> Self {
        let now = Utc::now();
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            identity_id: identity_id.to_string(),
            asset,
            limit,
            balance: None,
            authorized: false,
            peer_authorized: false,
            created_at: now,
            updated_at: now,
        }
    }

    pub fn with_balance(mut self, balance: f64) -> Self {
        self.balance = Some(balance);
        self
    }

    pub fn with_authorized(mut self, authorized: bool, peer_authorized: bool) -> Self {
        self.authorized = authorized;
        self.peer_authorized = peer_authorized;
        self
    }

    pub fn is_active(&self) -> bool {
        self.authorized && self.peer_authorized
    }

    pub fn get_balance(&self) -> Option<f64> {
        self.balance
    }

    pub fn get_limit(&self) -> Option<f64> {
        self.limit
    }

    pub fn set_limit(&mut self, limit: f64) {
        self.limit = Some(limit);
        self.updated_at = Utc::now();
    }

    pub fn set_balance(&mut self, balance: f64) {
        self.balance = Some(balance);
        self.updated_at = Utc::now();
    }
}

// ============================================================
// IDENTITY
// ============================================================
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identity {
    pub id: String,
    pub name: Option<String>,
    pub mnemonic: Option<String>,
    pub master_public_key: String,
    pub fingerprint: String,
    #[serde(with = "chrono::serde::ts_seconds")]
    pub created_at: DateTime<Utc>,
}

impl Identity {
    pub fn new(mnemonic: &str) -> Self {
        let mnemonic_obj = Mnemonic::parse_in_normalized(Language::English, mnemonic)
            .expect("Invalid mnemonic");
        let seed = mnemonic_obj.to_seed("");
        let seed_array: [u8; 32] = seed[..32].try_into().expect("seed slice length mismatch");
        let signing_key = SigningKey::from_bytes(&seed_array);
        let verifying_key = signing_key.verifying_key();
        let fingerprint = format!("{:x}", Sha256::digest(verifying_key.as_bytes()));

        Self {
            id: uuid::Uuid::new_v4().to_string(),
            name: None,
            mnemonic: Some(mnemonic.to_string()),
            master_public_key: hex::encode(verifying_key.as_bytes()),
            fingerprint,
            created_at: Utc::now(),
        }
    }

    pub fn generate() -> Self {
        let entropy: [u8; 16] = rand::thread_rng().gen();
        let mnemonic = Mnemonic::from_entropy_in(Language::English, &entropy)
            .expect("Failed to generate mnemonic");
        Self::new(&mnemonic.to_string())
    }
}

// ============================================================
// DATABASE (ESTESO CON TRUSTLINE)
// ============================================================
pub struct WalletDB {
    conn: Connection,
}

impl WalletDB {
    pub fn new(path: &str) -> SqlResult<Self> {
        let conn = Connection::open(path)?;
        
        // Tabella identities
        conn.execute(
            "CREATE TABLE IF NOT EXISTS identities (
                id TEXT PRIMARY KEY,
                name TEXT,
                mnemonic TEXT,
                master_public_key TEXT,
                fingerprint TEXT UNIQUE,
                created_at INTEGER
            )",
            [],
        )?;

        // 🔥 TABELLA TRUSTLINE
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

        // 🔥 INDICI
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trustlines_identity ON trustlines(identity_id)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trustlines_asset ON trustlines(network, asset_code, asset_issuer)",
            [],
        )?;

        Ok(Self { conn })
    }

    // ============================================================
    // IDENTITY - OPERAZIONI
    // ============================================================

    pub fn save_identity(&self, identity: &Identity) -> SqlResult<()> {
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
                identity.created_at.timestamp()
            ],
        )?;
        Ok(())
    }

    pub fn get_identity(&self, id: &str) -> SqlResult<Option<Identity>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, name, mnemonic, master_public_key, fingerprint, created_at 
             FROM identities WHERE id = ?1",
        )?;
        let mut rows = stmt.query(params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(Identity {
                id: row.get(0)?,
                name: row.get(1)?,
                mnemonic: row.get(2)?,
                master_public_key: row.get(3)?,
                fingerprint: row.get(4)?,
                created_at: DateTime::from_timestamp(row.get(5)?, 0)
                    .expect("Invalid timestamp"),
            }))
        } else {
            Ok(None)
        }
    }

    // ============================================================
    // TRUSTLINE - OPERAZIONI
    // ============================================================

    pub fn save_trustline(&self, trustline: &Trustline) -> SqlResult<()> {
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

    pub fn get_trustline(&self, id: &str) -> SqlResult<Option<Trustline>> {
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

    pub fn get_trustlines_by_identity(&self, identity_id: &str) -> SqlResult<Vec<Trustline>> {
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

    pub fn has_trustline(&self, identity_id: &str, network: &str, asset_code: &str, issuer: &Option<String>) -> SqlResult<bool> {
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

    pub fn delete_trustline(&self, id: &str) -> SqlResult<()> {
        self.conn.execute(
            "DELETE FROM trustlines WHERE id = ?1",
            params![id],
        )?;
        Ok(())
    }

    pub fn delete_trustline_by_asset(
        &self, 
        identity_id: &str, 
        network: &str, 
        asset_code: &str, 
        issuer: &Option<String>
    ) -> SqlResult<()> {
        self.conn.execute(
            "DELETE FROM trustlines 
             WHERE identity_id = ?1 AND network = ?2 AND asset_code = ?3 AND asset_issuer = ?4",
            params![identity_id, network, asset_code, issuer],
        )?;
        Ok(())
    }

    pub fn update_trustline_balance(&self, id: &str, balance: f64) -> SqlResult<()> {
        self.conn.execute(
            "UPDATE trustlines SET balance = ?1, updated_at = ?2 WHERE id = ?3",
            params![balance, Utc::now().timestamp(), id],
        )?;
        Ok(())
    }

    pub fn update_trustline_limit(&self, id: &str, limit: f64) -> SqlResult<()> {
        self.conn.execute(
            "UPDATE trustlines SET limit_amount = ?1, updated_at = ?2 WHERE id = ?3",
            params![limit, Utc::now().timestamp(), id],
        )?;
        Ok(())
    }

    fn _row_to_trustline(&self, row: &rusqlite::Row) -> SqlResult<Trustline> {
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
            created_at: DateTime::from_timestamp(row.get(10)?, 0).unwrap_or(Utc::now()),
            updated_at: DateTime::from_timestamp(row.get(11)?, 0).unwrap_or(Utc::now()),
        })
    }
}

// ============================================================
// NETWORK MANAGER (IL CUORE)
// ============================================================
pub struct NetworkManager {
    internet_available: bool,
    reticulum_available: bool,
}

impl NetworkManager {
    pub fn new() -> Self {
        Self {
            internet_available: true,
            reticulum_available: false,
        }
    }

    pub async fn send_via_internet(&self, url: &str, data: Vec<u8>) -> Result<String, reqwest::Error> {
        let client = reqwest::Client::new();
        let response = client
            .post(url)
            .json(&data)
            .send()
            .await?;
        Ok(response.text().await?)
    }

    pub fn send_via_reticulum(&self, _data: Vec<u8>) -> Result<String, String> {
        // TODO: Implementare Reticulum
        Ok("Sent via Reticulum".to_string())
    }

    pub fn send(&self, data: Vec<u8>) -> Result<String, String> {
        if self.internet_available {
            Ok("Sent via Internet".to_string())
        } else if self.reticulum_available {
            self.send_via_reticulum(data)
        } else {
            Err("No network available".to_string())
        }
    }
}

// ============================================================
// PYTHON FFI (solo su richiesta)
// ============================================================
#[cfg(feature = "python")]
#[pymodule]
fn wallet_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyIdentity>()?;
    m.add_class::<PyAsset>()?;
    m.add_class::<PyWalletDB>()?;
    m.add_class::<PyTrustline>()?;  // 🔥 NUOVO
    m.add_function(wrap_pyfunction!(create_wallet, m)?)?;
    m.add_function(wrap_pyfunction!(create_trustline, m)?)?;  // 🔥 NUOVO
    Ok(())
}

#[cfg(feature = "python")]
#[pyclass]
struct PyIdentity {
    inner: Identity,
}

#[cfg(feature = "python")]
#[pymethods]
impl PyIdentity {
    #[new]
    fn new(mnemonic: Option<&str>) -> Self {
        let default_mnemonic = {
            let entropy: [u8; 16] = rand::thread_rng().gen();
            Mnemonic::from_entropy_in(Language::English, &entropy)
                .expect("Failed to generate mnemonic")
                .to_string()
        };
        let mnemonic = mnemonic.unwrap_or(&default_mnemonic);
        Self {
            inner: Identity::new(mnemonic),
        }
    }

    fn fingerprint(&self) -> String {
        self.inner.fingerprint.clone()
    }

    fn id(&self) -> String {
        self.inner.id.clone()
    }

    fn name(&self) -> Option<String> {
        self.inner.name.clone()
    }

    fn mnemonic(&self) -> Option<String> {
        self.inner.mnemonic.clone()
    }
}

#[cfg(feature = "python")]
#[pyclass]
struct PyAsset {
    inner: Asset,
}

#[cfg(feature = "python")]
#[pymethods]
impl PyAsset {
    #[staticmethod]
    fn xrp() -> Self {
        Self {
            inner: Asset::xrp(),
        }
    }

    #[staticmethod]
    fn xlm() -> Self {
        Self {
            inner: Asset::xlm(),
        }
    }

    #[staticmethod]
    fn rlusd() -> Self {
        Self {
            inner: Asset::rlusd(),
        }
    }

    fn __repr__(&self) -> String {
        format!("{}", self.inner)
    }
}

#[cfg(feature = "python")]
#[pyclass]
struct PyWalletDB {
    inner: WalletDB,
}

#[cfg(feature = "python")]
#[pymethods]
impl PyWalletDB {
    #[new]
    fn new(path: &str) -> PyResult<Self> {
        Ok(Self {
            inner: WalletDB::new(path).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
            })?,
        })
    }

    // ---- IDENTITY ----

    fn save_identity(&self, identity: &PyIdentity) -> PyResult<()> {
        self.inner.save_identity(&identity.inner).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
        })
    }

    fn get_identity(&self, id: &str) -> PyResult<Option<PyIdentity>> {
        self.inner
            .get_identity(id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
            .map(|opt| opt.map(|id| PyIdentity { inner: id }))
    }

    // ---- TRUSTLINE (NUOVE) ----

    fn save_trustline(&self, trustline: &PyTrustline) -> PyResult<()> {
        self.inner.save_trustline(&trustline.inner).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
        })
    }

    fn get_trustline(&self, id: &str) -> PyResult<Option<PyTrustline>> {
        self.inner
            .get_trustline(id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
            .map(|opt| opt.map(|tl| PyTrustline { inner: tl }))
    }

    fn get_trustlines_by_identity(&self, identity_id: &str) -> PyResult<Vec<PyTrustline>> {
        self.inner
            .get_trustlines_by_identity(identity_id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
            .map(|vec| vec.into_iter().map(|tl| PyTrustline { inner: tl }).collect())
    }

    fn has_trustline(&self, identity_id: &str, network: &str, asset_code: &str, issuer: Option<&str>) -> PyResult<bool> {
        self.inner
            .has_trustline(identity_id, network, asset_code, &issuer.map(|s| s.to_string()))
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
    }

    fn delete_trustline(&self, id: &str) -> PyResult<()> {
        self.inner
            .delete_trustline(id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
    }
}

// ============================================================
// PYTHON TRUSTLINE (NUOVO)
// ============================================================

#[cfg(feature = "python")]
#[pyclass]
struct PyTrustline {
    inner: Trustline,
}

#[cfg(feature = "python")]
#[pymethods]
impl PyTrustline {
    #[new]
    fn new(identity_id: &str, asset: &PyAsset, limit: Option<f64>) -> Self {
        Self {
            inner: Trustline::new(identity_id, asset.inner.clone(), limit),
        }
    }

    fn id(&self) -> String {
        self.inner.id.clone()
    }

    fn identity_id(&self) -> String {
        self.inner.identity_id.clone()
    }

    fn asset(&self) -> PyAsset {
        PyAsset {
            inner: self.inner.asset.clone(),
        }
    }

    fn limit(&self) -> Option<f64> {
        self.inner.limit
    }

    fn balance(&self) -> Option<f64> {
        self.inner.balance
    }

    fn authorized(&self) -> bool {
        self.inner.authorized
    }

    fn peer_authorized(&self) -> bool {
        self.inner.peer_authorized
    }

    fn is_active(&self) -> bool {
        self.inner.is_active()
    }

    fn set_limit(&mut self, limit: f64) {
        self.inner.set_limit(limit);
    }

    fn set_balance(&mut self, balance: f64) {
        self.inner.set_balance(balance);
    }

    fn with_balance(&self, balance: f64) -> PyTrustline {
        PyTrustline {
            inner: self.inner.clone().with_balance(balance),
        }
    }

    fn with_authorized(&self, authorized: bool, peer_authorized: bool) -> PyTrustline {
        PyTrustline {
            inner: self.inner.clone().with_authorized(authorized, peer_authorized),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Trustline({} -> {} | limit: {:?} | balance: {:?} | active: {})",
            self.inner.identity_id,
            self.inner.asset,
            self.inner.limit,
            self.inner.balance,
            self.inner.is_active()
        )
    }
}

// ============================================================
// PYTHON FUNCTIONS
// ============================================================

#[cfg(feature = "python")]
#[pyfunction]
fn create_wallet(db_path: &str, name: Option<&str>) -> PyResult<String> {
    let db = WalletDB::new(db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    let identity = Identity::generate();

    if let Some(n) = name {
        let mut id = identity;
        id.name = Some(n.to_string());
        db.save_identity(&id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        Ok(id.id)
    } else {
        db.save_identity(&identity)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        Ok(identity.id)
    }
}

// 🔥 NUOVA FUNZIONE: crea una trustline
#[cfg(feature = "python")]
#[pyfunction]
fn create_trustline(db_path: &str, identity_id: &str, network: &str, asset_code: &str, issuer: Option<&str>, limit: Option<f64>) -> PyResult<String> {
    let db = WalletDB::new(db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    
    let network_enum = match network {
        "XRPL" => Network::XRPL,
        "Stellar" => Network::Stellar,
        "Bitcoin" => Network::Bitcoin,
        "Ethereum" => Network::Ethereum,
        "Monero" => Network::Monero,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Network non supportato: {}", network)
        )),
    };
    
    let asset = Asset::new(network_enum, asset_code, 6);
    let asset = if let Some(iss) = issuer {
        asset.with_issuer(iss)
    } else {
        asset
    };
    
    let trustline = Trustline::new(identity_id, asset, limit);
    
    db.save_trustline(&trustline)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    
    Ok(trustline.id)
}