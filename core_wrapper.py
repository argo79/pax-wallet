#!/usr/bin/env python3
"""
wallet_core.py - Wrapper Python per il Core Rust
Carica la libreria compilata e fornisce un'interfaccia pulita
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import json

# ============================================================
# 1. CARICA IL CORE RUST
# ============================================================

def get_core_path() -> Path:
    """Trova il percorso del modulo core compilato"""
    # Cerca nella root del progetto
    possible_paths = [
        Path(__file__).parent / "wallet_core.so",
        Path(__file__).parent / "target/release/libwallet_core.so",
        Path(__file__).parent / "target/debug/libwallet_core.so",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError("wallet_core.so non trovato. Esegui prima cargo build")

# ============================================================
# 2. CARICA IL MODULO RUST
# ============================================================

# Aggiungi la directory del core al path
core_path = get_core_path()
sys.path.insert(0, str(core_path.parent))

try:
    import wallet_core as _rust
    print("✅ Core Rust caricato con successo")
except ImportError as e:
    print(f"❌ Errore caricamento Core Rust: {e}")
    print("   Assicurati di aver compilato con: cargo build --release")
    print("   e copiato il file come: cp target/release/libwallet_core.so wallet_core.so")
    raise

# ============================================================
# 3. CLASSE WRAPPER
# ============================================================

class CoreWallet:
    """
    Wrapper Python per il Core Rust
    Fornisce un'interfaccia pulita per gestire identità e asset
    """
    
    def __init__(self, db_path: str = "core.db"):
        self.db_path = db_path
        self.db = _rust.PyWalletDB(db_path)
        self._current_identity: Optional[Any] = None
    
    # ============================================================
    # IDENTITA'
    # ============================================================
    
    def create_identity(self, name: str = None) -> str:
        """Crea una nuova identità con nome opzionale"""
        identity_id = _rust.create_wallet(self.db_path, name)
        self._current_identity = self.db.get_identity(identity_id)
        return identity_id
    
    def get_identity(self, identity_id: str) -> Optional[Any]:
        """Recupera un'identità esistente"""
        return self.db.get_identity(identity_id)
    
    def get_current_identity(self) -> Optional[Any]:
        """Recupera l'identità corrente"""
        return self._current_identity
    
    def list_identities(self) -> List[Dict[str, str]]:
        """Lista tutte le identità nel database"""
        # TODO: Implementare query SQL
        return []
    
    def delete_identity(self, identity_id: str) -> bool:
        """Elimina un'identità"""
        # TODO: Implementare delete
        return False
    
    # ============================================================
    # ASSET
    # ============================================================
    
    def get_asset(self, asset_type: str) -> Any:
        """Crea un oggetto asset"""
        if asset_type == "XRP":
            return _rust.PyAsset.xrp()
        elif asset_type == "XLM":
            return _rust.PyAsset.xlm()
        elif asset_type == "RLUSD":
            return _rust.PyAsset.rlusd()
        else:
            raise ValueError(f"Asset non supportato: {asset_type}")
    
    def get_supported_assets(self) -> List[str]:
        """Lista degli asset supportati"""
        return ["XRP", "XLM", "RLUSD"]
    
    # ============================================================
    # DERIVAZIONE
    # ============================================================
    
    def derive_key(self, identity_id: str, network: str, index: int = 0) -> str:
        """Deriva una chiave per una specifica blockchain"""
        identity = self.db.get_identity(identity_id)
        if not identity:
            raise ValueError(f"Identità {identity_id} non trovata")
        
        # Implementazione di derivazione in Rust
        # TODO: Aggiungere metodo derive_key al Core
        return identity.fingerprint()  # Placeholder
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def info(self) -> Dict[str, Any]:
        """Informazioni sul core"""
        return {
            "version": "0.1.0",
            "db_path": self.db_path,
            "current_identity": self._current_identity.id() if self._current_identity else None,
            "supported_assets": self.get_supported_assets(),
        }
    
    def close(self):
        """Chiudi il database"""
        # TODO: Implementare close
        pass


# ============================================================
# 4. FUNZIONE FACTORY
# ============================================================

def create_core(db_path: str = "core.db") -> CoreWallet:
    """Crea un'istanza del Core Wallet"""
    return CoreWallet(db_path)


# ============================================================
# 5. TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST CORE WRAPPER")
    print("=" * 60)
    
    # Crea il core
    core = create_core("test_core.db")
    
    # Crea identità
    print("\n📤 Creazione identità...")
    identity_id = core.create_identity("Test User")
    print(f"   ID: {identity_id}")
    
    # Recupera identità
    identity = core.get_identity(identity_id)
    print(f"   Fingerprint: {identity.fingerprint()}")
    
    # Asset
    print("\n📊 Asset disponibili:")
    for asset in core.get_supported_assets():
        a = core.get_asset(asset)
        print(f"   - {a}")
    
    # Info
    print("\n📊 Info core:")
    info = core.info()
    print(f"   {info}")
    
    print("\n✅ Test completato!")