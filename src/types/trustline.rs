// src/types/trustline.rs

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use crate::types::asset::Asset;

// ============================================================
// TRUSTLINE
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

// ============================================================
// REQUEST PER CREAZIONE TRUSTLINE
// ============================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustlineRequest {
    pub asset: Asset,
    pub limit: Option<f64>,
}

// ============================================================
// METODI
// ============================================================

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

    pub fn has_balance(&self) -> bool {
        self.balance.is_some()
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
// TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::asset::{Asset, Network};

    #[test]
    fn test_trustline_creation() {
        let asset = Asset::rlusd();
        let identity_id = "test-identity";
        
        let trustline = Trustline::new(identity_id, asset, Some(1000.0));
        
        assert_eq!(trustline.identity_id, identity_id);
        assert_eq!(trustline.asset.code, "RLUSD");
        assert_eq!(trustline.limit, Some(1000.0));
        assert!(!trustline.authorized);
    }

    #[test]
    fn test_trustline_with_balance() {
        let asset = Asset::xrp();
        let identity_id = "test-identity";
        
        let trustline = Trustline::new(identity_id, asset, None)
            .with_balance(150.5)
            .with_authorized(true, true);
        
        assert_eq!(trustline.balance, Some(150.5));
        assert!(trustline.authorized);
        assert!(trustline.peer_authorized);
        assert!(trustline.is_active());
    }
}