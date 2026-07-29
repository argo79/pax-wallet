use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Network {
    XRPL,
    Stellar,
    Bitcoin,
    Ethereum,
    Monero,
    Custom(String),
}

impl fmt::Display for Network {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Network::XRPL => write!(f, "XRPL"),
            Network::Stellar => write!(f, "Stellar"),
            Network::Bitcoin => write!(f, "Bitcoin"),
            Network::Ethereum => write!(f, "Ethereum"),
            Network::Monero => write!(f, "Monero"),
            Network::Custom(s) => write!(f, "{}", s),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Asset {
    pub network: Network,
    pub issuer: Option<String>,  // XRP: r..., Stellar: G..., ETH: 0x...
    pub code: String,            // XRP, XLM, RLUSD, EURC, USDC, BTC, ETH
    pub decimals: u8,
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

    // Asset predefiniti per comodità
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

    pub fn usdc_stellar() -> Self {
        Self::new(Network::Stellar, "USDC", 7)
            .with_issuer("GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
    }

    pub fn eurc_stellar() -> Self {
        Self::new(Network::Stellar, "EURC", 7)
            .with_issuer("G...") // metti l'issuer corretto
    }
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