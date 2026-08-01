#!/usr/bin/env python3
"""
core_wrapper.py - Wrapper Python per il Core Rust
Versione COMPLETA con Trustline e Identity
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
import json

# ============================================================
# 1. CARICA IL CORE RUST
# ============================================================

def get_core_path() -> Path:
    """Trova il percorso del modulo core compilato"""
    possible_paths = [
        Path(__file__).parent / "wallet_core.so",
        Path(__file__).parent / "target/release/libwallet_core.so",
        Path(__file__).parent / "target/debug/libwallet_core.so",
        Path(__file__).parent / "wallet_core.dll",  # Windows
        Path(__file__).parent / "wallet_core.dylib",  # macOS
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(
        "wallet_core non trovato. Esegui: cargo build --release"
    )

# Carica il modulo Rust
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
# 2. DATACLASS PER TRUSTLINE (Python-friendly)
# ============================================================

@dataclass
class TrustlineInfo:
    """Rappresentazione Python di una trustline"""
    id: str
    identity_id: str
    network: str
    asset_code: str
    asset_issuer: Optional[str]
    decimals: int
    limit: Optional[float]
    balance: Optional[float]
    authorized: bool
    peer_authorized: bool
    is_active: bool
    
    @classmethod
    def from_rust(cls, rust_trustline) -> 'TrustlineInfo':
        """Converte da PyTrustline a dataclass Python"""
        return cls(
            id=rust_trustline.id(),
            identity_id=rust_trustline.identity_id(),
            network=str(rust_trustline.asset().inner.network),
            asset_code=rust_trustline.asset().inner.code,
            asset_issuer=rust_trustline.asset().inner.issuer,
            decimals=rust_trustline.asset().inner.decimals,
            limit=rust_trustline.limit(),
            balance=rust_trustline.balance(),
            authorized=rust_trustline.authorized(),
            peer_authorized=rust_trustline.peer_authorized(),
            is_active=rust_trustline.is_active()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "identity_id": self.identity_id,
            "network": self.network,
            "asset_code": self.asset_code,
            "asset_issuer": self.asset_issuer,
            "decimals": self.decimals,
            "limit": self.limit,
            "balance": self.balance,
            "authorized": self.authorized,
            "peer_authorized": self.peer_authorized,
            "is_active": self.is_active
        }

# ============================================================
# 3. CLASSE CORE WALLET COMPLETA
# ============================================================

class CoreWallet:
    """
    Wrapper completo per il Core Rust
    Gestisce Identity, Asset e Trustline
    """
    
    def __init__(self, db_path: str = "core.db"):
        self.db_path = db_path
        self.db = _rust.PyWalletDB(db_path)
        self._current_identity: Optional[Any] = None
        self._cache = {
            "trustlines": {},  # identity_id → list of TrustlineInfo
            "identities": {},  # identity_id → Identity
        }
    
    # ============================================================
    # IDENTITA'
    # ============================================================
    
    def create_identity(self, name: Optional[str] = None) -> str:
        """Crea una nuova identità"""
        identity_id = _rust.create_wallet(self.db_path, name)
        self._current_identity = self.db.get_identity(identity_id)
        return identity_id
    
    def get_identity(self, identity_id: str) -> Optional[Any]:
        """Recupera un'identità"""
        return self.db.get_identity(identity_id)
    
    def get_current_identity(self) -> Optional[Any]:
        """Recupera l'identità corrente"""
        return self._current_identity
    
    def get_current_identity_id(self) -> Optional[str]:
        """ID dell'identità corrente"""
        if self._current_identity:
            return self._current_identity.id()
        return None
    
    def list_identities(self) -> List[Dict[str, str]]:
        """Lista tutte le identità - USA SQLITE DIRETTO"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verifica che la tabella esista
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='identities'")
            if not cursor.fetchone():
                conn.close()
                return []
            
            cursor.execute("SELECT id, name, fingerprint FROM identities")
            rows = cursor.fetchall()
            conn.close()
            
            return [{"id": r[0], "name": r[1] or "", "fingerprint": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Error listing identities: {e}")
            return []
    
    def delete_identity(self, identity_id: str) -> bool:
        """Elimina un'identità e tutte le sue trustline"""
        # TODO: Implementare delete con cascade
        return False
    
    # ============================================================
    # ASSET
    # ============================================================
    
    def get_asset(self, asset_type: str) -> Any:
        """Crea un oggetto asset Rust"""
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
    
    def create_custom_asset(self, network: str, code: str, issuer: Optional[str] = None, decimals: int = 6) -> Any:
        """Crea un asset personalizzato"""
        # Mappa network string → Network enum
        network_map = {
            "XRPL": _rust.Network.XRPL,
            "Stellar": _rust.Network.Stellar,
            "Bitcoin": _rust.Network.Bitcoin,
            "Ethereum": _rust.Network.Ethereum,
            "Monero": _rust.Network.Monero,
        }
        
        if network not in network_map:
            raise ValueError(f"Network non supportato: {network}")
        
        # TODO: Implementare creazione asset in Rust
        # Per ora usiamo XRP come fallback
        return _rust.PyAsset.xrp()
    
    # ============================================================
    # TRUSTLINE (NUOVA IMPLEMENTAZIONE COMPLETA)
    # ============================================================
    
    def create_trustline(
        self, 
        identity_id: str, 
        network: str, 
        asset_code: str, 
        issuer: Optional[str] = None,
        limit: Optional[float] = None
    ) -> str:
        """
        Crea una nuova trustline nel database
        """
        rust_trustline = _rust.create_trustline(
            self.db_path,
            identity_id,
            network,
            asset_code,
            issuer,
            limit
        )
        return rust_trustline
    
    def get_trustline(self, trustline_id: str) -> Optional[TrustlineInfo]:
        """Recupera una trustline"""
        rust_tl = self.db.get_trustline(trustline_id)
        if rust_tl:
            return TrustlineInfo.from_rust(rust_tl)
        return None
    
    def get_trustlines(self, identity_id: Optional[str] = None) -> List[TrustlineInfo]:
        """Recupera tutte le trustline di un'identità"""
        if identity_id is None:
            identity_id = self.get_current_identity_id()
            if identity_id is None:
                return []
        
        # Controlla cache
        if identity_id in self._cache["trustlines"]:
            return self._cache["trustlines"][identity_id]
        
        # Recupera da Rust
        rust_trustlines = self.db.get_trustlines_by_identity(identity_id)
        trustlines = [TrustlineInfo.from_rust(tl) for tl in rust_trustlines]
        
        # Aggiorna cache
        self._cache["trustlines"][identity_id] = trustlines
        return trustlines
    
    def has_trustline(
        self, 
        identity_id: str, 
        network: str, 
        asset_code: str, 
        issuer: Optional[str] = None
    ) -> bool:
        """Verifica se esiste una trustline"""
        return self.db.has_trustline(identity_id, network, asset_code, issuer)
    
    def delete_trustline(self, trustline_id: str) -> bool:
        """Elimina una trustline"""
        try:
            self.db.delete_trustline(trustline_id)
            # Invalida cache
            self._cache["trustlines"].clear()
            return True
        except Exception as e:
            print(f"Errore eliminazione trustline: {e}")
            return False
    
    def delete_trustline_by_asset(
        self, 
        identity_id: str, 
        network: str, 
        asset_code: str, 
        issuer: Optional[str] = None
    ) -> bool:
        """Elimina una trustline per asset"""
        # TODO: Aggiungere metodo al Rust
        # Per ora, cerchiamo e cancelliamo per ID
        trustlines = self.get_trustlines(identity_id)
        for tl in trustlines:
            if (tl.network == network and 
                tl.asset_code == asset_code and 
                tl.asset_issuer == issuer):
                return self.delete_trustline(tl.id)
        return False
    
    def update_trustline_balance(self, trustline_id: str, balance: float) -> bool:
        """Aggiorna il balance di una trustline"""
        try:
            # TODO: Aggiungere metodo update_trustline_balance al Rust
            # Per ora, usiamo il save
            rust_tl = self.db.get_trustline(trustline_id)
            if rust_tl:
                rust_tl.set_balance(balance)
                self.db.save_trustline(rust_tl)
                # Invalida cache
                self._cache["trustlines"].clear()
                return True
            return False
        except Exception as e:
            print(f"Errore aggiornamento balance: {e}")
            return False
    
    def update_trustline_limit(self, trustline_id: str, limit: float) -> bool:
        """Aggiorna il limit di una trustline"""
        try:
            rust_tl = self.db.get_trustline(trustline_id)
            if rust_tl:
                rust_tl.set_limit(limit)
                self.db.save_trustline(rust_tl)
                # Invalida cache
                self._cache["trustlines"].clear()
                return True
            return False
        except Exception as e:
            print(f"Errore aggiornamento limit: {e}")
            return False
    
    def get_trustline_balance(self, identity_id: str, asset_code: str, issuer: Optional[str] = None) -> Optional[float]:
        """Recupera il balance di una trustline specifica"""
        trustlines = self.get_trustlines(identity_id)
        for tl in trustlines:
            if tl.asset_code == asset_code and tl.asset_issuer == issuer:
                return tl.balance
        return None
    
    def trustline_to_dict(self, trustline: Union[TrustlineInfo, str]) -> Dict[str, Any]:
        """Converte trustline in dict"""
        if isinstance(trustline, str):
            trustline = self.get_trustline(trustline)
            if trustline is None:
                return {}
        return trustline.to_dict()
    
    # ============================================================
    # DERIVAZIONE CHIAVI
    # ============================================================
    
    def derive_key(self, identity_id: str, network: str, index: int = 0) -> str:
        """Deriva una chiave per una specifica blockchain"""
        identity = self.db.get_identity(identity_id)
        if not identity:
            raise ValueError(f"Identità {identity_id} non trovata")
        
        # TODO: Implementare derivazione in Rust
        # Usa fingerprint come placeholder
        return identity.fingerprint()
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def info(self) -> Dict[str, Any]:
        """Informazioni sul core"""
        trustlines_count = len(self.get_trustlines())
        
        return {
            "version": "0.1.0",
            "db_path": self.db_path,
            "current_identity": self.get_current_identity_id(),
            "supported_assets": self.get_supported_assets(),
            "trustlines_count": trustlines_count,
        }
    
    def clear_cache(self):
        """Pulisce la cache"""
        self._cache = {
            "trustlines": {},
            "identities": {},
        }
    
    def close(self):
        """Chiude il database"""
        # SQLite gestisce automaticamente la chiusura
        self.clear_cache()
        self._current_identity = None
        self.db = None
        print("✅ Core chiuso")


# ============================================================
# 4. FUNZIONI FACTORY
# ============================================================

def create_core(db_path: str = "core.db") -> CoreWallet:
    """Crea un'istanza del Core Wallet"""
    return CoreWallet(db_path)


def get_core_version() -> str:
    """Versione del core"""
    return "0.1.0"

# ============================================================
# 5. INTEGRAZIONE CON wallet_manager.py
# ============================================================

class CoreIntegration:
    """
    Ponte tra wallet_manager.py e CoreWallet
    """
    
    def __init__(self, core: CoreWallet):
        self.core = core
        self._identity_id: Optional[str] = None
    
    def set_identity(self, identity_id: str):
        """Imposta l'identità corrente"""
        self._identity_id = identity_id
    
    def get_identity(self) -> Optional[str]:
        return self._identity_id
    
    def sync_trustlines(self, manager_trustlines: List[Dict]) -> List[TrustlineInfo]:
        """
        Sincronizza le trustline da wallet_manager.py
        """
        if not self._identity_id:
            raise ValueError("Nessuna identità impostata")
        
        # Elimina tutte le trustline esistenti
        existing = self.core.get_trustlines(self._identity_id)
        for tl in existing:
            self.core.delete_trustline(tl.id)
        
        # Crea nuove trustline
        results = []
        for tl_data in manager_trustlines:
            # Determina network
            network = tl_data.get("network", "XRPL")
            if network == "Stellar":
                network = "Stellar"
            elif network == "XLM":
                network = "Stellar"
            else:
                network = "XRPL"
            
            # Crea trustline
            asset_code = tl_data.get("currency") or tl_data.get("asset_code")
            issuer = tl_data.get("issuer") or tl_data.get("asset_issuer")
            limit = tl_data.get("limit")
            
            if not asset_code or not issuer:
                continue
            
            try:
                rust_id = self.core.create_trustline(
                    self._identity_id,
                    network,
                    asset_code,
                    issuer,
                    limit
                )
                # Recupera la trustline creata
                tl_info = self.core.get_trustline(rust_id)
                if tl_info:
                    results.append(tl_info)
            except Exception as e:
                print(f"Errore sincronizzazione trustline: {e}")
        
        return results
    
    def import_trustline_from_xrp(self, xrp_trustline: Dict) -> Optional[TrustlineInfo]:
        """
        Importa una trustline XRP nel core
        """
        if not self._identity_id:
            raise ValueError("Nessuna identità impostata")
        
        network = "XRPL"
        asset_code = xrp_trustline.get("currency")
        issuer = xrp_trustline.get("issuer")
        limit = xrp_trustline.get("limit")
        balance = xrp_trustline.get("balance")
        
        if not asset_code or not issuer:
            return None
        
        # Crea trustline
        rust_id = self.core.create_trustline(
            self._identity_id,
            network,
            asset_code,
            issuer,
            limit
        )
        
        # Aggiorna balance se disponibile
        if balance is not None:
            self.core.update_trustline_balance(rust_id, balance)
        
        return self.core.get_trustline(rust_id)

# ============================================================
# 6. TEST COMPLETO
# ============================================================

if __name__ == "__main__":
    import tempfile
    import os
    
    print("=" * 60)
    print("🧪 TEST COMPLETO CORE WRAPPER")
    print("=" * 60)
    
    # Crea un database temporaneo
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_core.db")
        core = create_core(db_path)
        
        # 1. Crea identità
        print("\n📤 1. Creazione identità...")
        identity_id = core.create_identity("Test User")
        print(f"   ✅ ID: {identity_id}")
        
        # 2. Verifica identità
        print("\n📤 2. Verifica identità...")
        identity = core.get_identity(identity_id)
        print(f"   Fingerprint: {identity.fingerprint()}")
        print(f"   Name: {identity.name()}")
        
        # 3. Crea asset
        print("\n📊 3. Asset disponibili...")
        for asset_name in core.get_supported_assets():
            asset = core.get_asset(asset_name)
            print(f"   - {asset}")
        
        # 4. Crea trustline
        print("\n🔗 4. Creazione trustline...")
        try:
            trustline_id = core.create_trustline(
                identity_id,
                "XRPL",
                "RLUSD",
                "rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth",
                10000.0
            )
            print(f"   ✅ Trustline ID: {trustline_id}")
            
            # 5. Recupera trustline
            print("\n🔗 5. Recupero trustline...")
            tl = core.get_trustline(trustline_id)
            print(f"   ID: {tl.id}")
            print(f"   Asset: {tl.asset_code}")
            print(f"   Issuer: {tl.asset_issuer}")
            print(f"   Limit: {tl.limit}")
            print(f"   Active: {tl.is_active}")
            
            # 6. Lista trustline
            print("\n🔗 6. Lista trustline...")
            trustlines = core.get_trustlines(identity_id)
            for tl in trustlines:
                print(f"   - {tl.asset_code} @ {tl.asset_issuer} (limit: {tl.limit})")
            
            # 7. Aggiorna balance
            print("\n🔗 7. Aggiornamento balance...")
            core.update_trustline_balance(trustline_id, 150.75)
            tl_updated = core.get_trustline(trustline_id)
            print(f"   Nuovo balance: {tl_updated.balance}")
            
        except Exception as e:
            print(f"   ❌ Errore: {e}")
        
        # 8. Info
        print("\n📊 8. Info core...")
        info = core.info()
        print(f"   {json.dumps(info, indent=2)}")
        
        print("\n✅ Test completato!")