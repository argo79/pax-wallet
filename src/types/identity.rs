use serde::{Deserialize, Serialize};
use ed25519_dalek::{SigningKey, VerifyingKey};
use bip39::{Mnemonic, Language, Seed};
use sha2::{Sha256, Digest};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identity {
    pub id: String,              // UUID o fingerprint
    pub name: Option<String>,    // "Marco"
    pub mnemonic: Option<String>, // BIP39 seed phrase (cifrato)
    pub master_public_key: String,
    pub fingerprint: String,     // Hash dell'identità
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DerivedKey {
    pub network: Network,
    pub public_key: String,
    pub private_key_encrypted: Vec<u8>, // Cifrato con AES
    pub derivation_path: String,
}

impl Identity {
    pub fn new(mnemonic: &str) -> Self {
        let mnemonic = Mnemonic::from_phrase(mnemonic, Language::English)
            .expect("Invalid mnemonic");
        let seed = Seed::new(&mnemonic, "");
        
        // Deriva la chiave master (Ed25519)
        let signing_key = SigningKey::from_bytes(&seed.as_bytes()[..32]);
        let verifying_key = signing_key.verifying_key();
        
        let fingerprint = format!("{:x}", Sha256::digest(verifying_key.as_bytes()));
        
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            name: None,
            mnemonic: Some(mnemonic.to_string()),
            master_public_key: hex::encode(verifying_key.as_bytes()),
            fingerprint,
            created_at: chrono::Utc::now(),
        }
    }

    // Deriva una chiave per una specifica blockchain
    pub fn derive_key(&self, network: Network, index: u32) -> DerivedKey {
        // Implementazione con BIP32/44
        // Per ora: placeholder
        DerivedKey {
            network,
            public_key: "".to_string(),
            private_key_encrypted: vec![],
            derivation_path: format!("m/44'/{}'/0'/0/{}", index, index),
        }
    }
}