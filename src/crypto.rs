// src/crypto.rs
use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce,
};
use pbkdf2::pbkdf2_hmac;
use sha2::Sha256;
use rand::{Rng, thread_rng};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine};

const SALT_SIZE: usize = 16;
const NONCE_SIZE: usize = 12;
const ITERATIONS: u32 = 200_000;

fn derive_key(password: &str, salt: &[u8; SALT_SIZE]) -> [u8; 32] {
    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(password.as_bytes(), salt, ITERATIONS, &mut key);
    key
}

pub fn encrypt(plaintext: &str, password: &str) -> String {
    let mut rng = thread_rng();
    let mut salt = [0u8; SALT_SIZE];
    let mut nonce = [0u8; NONCE_SIZE];
    rng.fill(&mut salt);
    rng.fill(&mut nonce);
    
    let key = derive_key(password, &salt);
    let cipher = Aes256Gcm::new(&key.into());
    let nonce = Nonce::from_slice(&nonce);
    
    let ciphertext = cipher.encrypt(nonce, plaintext.as_bytes())
        .expect("encryption failed");
    
    let mut result = Vec::with_capacity(SALT_SIZE + NONCE_SIZE + ciphertext.len());
    result.extend_from_slice(&salt);
    result.extend_from_slice(&nonce);
    result.extend_from_slice(&ciphertext);
    
    BASE64.encode(result)
}

pub fn decrypt(encrypted_b64: &str, password: &str) -> Result<String, String> {
    let data = BASE64.decode(encrypted_b64)
        .map_err(|e| format!("Base64 decode error: {}", e))?;
    
    if data.len() < SALT_SIZE + NONCE_SIZE {
        return Err("Data too short".to_string());
    }
    
    let salt: [u8; SALT_SIZE] = data[..SALT_SIZE].try_into()
        .map_err(|_| "Invalid salt".to_string())?;
    let nonce: [u8; NONCE_SIZE] = data[SALT_SIZE..SALT_SIZE+NONCE_SIZE].try_into()
        .map_err(|_| "Invalid nonce".to_string())?;
    let ciphertext = &data[SALT_SIZE+NONCE_SIZE..];
    
    let key = derive_key(password, &salt);
    let cipher = Aes256Gcm::new(&key.into());
    let nonce = Nonce::from_slice(&nonce);
    
    let plaintext = cipher.decrypt(nonce, ciphertext)
        .map_err(|_| "Decryption failed (wrong password?)".to_string())?;
    
    String::from_utf8(plaintext).map_err(|e| format!("UTF-8 error: {}", e))
}

pub fn is_encrypted(data: &str) -> bool {
    if data.is_empty() || data.starts_with('{') {
        return false;
    }
    BASE64.decode(data).is_ok()
}

pub fn encrypt_bytes(data: &[u8], password: &str) -> String {
    let mut rng = thread_rng();
    let mut salt = [0u8; SALT_SIZE];
    let mut nonce = [0u8; NONCE_SIZE];
    rng.fill(&mut salt);
    rng.fill(&mut nonce);
    
    let key = derive_key(password, &salt);
    let cipher = Aes256Gcm::new(&key.into());
    let nonce = Nonce::from_slice(&nonce);
    
    let ciphertext = cipher.encrypt(nonce, data)
        .expect("encryption failed");
    
    let mut result = Vec::with_capacity(SALT_SIZE + NONCE_SIZE + ciphertext.len());
    result.extend_from_slice(&salt);
    result.extend_from_slice(&nonce);
    result.extend_from_slice(&ciphertext);
    
    BASE64.encode(result)
}

pub fn decrypt_bytes(encrypted_b64: &str, password: &str) -> Result<Vec<u8>, String> {
    let data = BASE64.decode(encrypted_b64)
        .map_err(|e| format!("Base64 decode error: {}", e))?;
    
    if data.len() < SALT_SIZE + NONCE_SIZE {
        return Err("Data too short".to_string());
    }
    
    let salt: [u8; SALT_SIZE] = data[..SALT_SIZE].try_into()
        .map_err(|_| "Invalid salt".to_string())?;
    let nonce: [u8; NONCE_SIZE] = data[SALT_SIZE..SALT_SIZE+NONCE_SIZE].try_into()
        .map_err(|_| "Invalid nonce".to_string())?;
    let ciphertext = &data[SALT_SIZE+NONCE_SIZE..];
    
    let key = derive_key(password, &salt);
    let cipher = Aes256Gcm::new(&key.into());
    let nonce = Nonce::from_slice(&nonce);
    
    let plaintext = cipher.decrypt(nonce, ciphertext)
        .map_err(|_| "Decryption failed (wrong password?)".to_string())?;
    
    Ok(plaintext)
}