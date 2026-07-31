#!/usr/bin/env python3
"""
wallet_api.py - API unificata per wallet XRP/XLM
Integra il Core Rust con i plugin esistenti
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
import json
import logging

# ============================================================
# 1. IMPORTA IL CORE WRAPPER
# ============================================================

from core_wrapper import create_core, CoreWallet, get_core_path

# ============================================================
# 2. IMPORTA I PLUGIN
# ============================================================

try:
    import wallet_manager as wm
    from wallet_manager import HybridXRPManager, CryptoType, NetworkType
    PLUGIN_XRP_AVAILABLE = True
    print("✅ Plugin XRP/XLM caricato")
except ImportError as e:
    PLUGIN_XRP_AVAILABLE = False
    print(f"⚠️ Plugin XRP/XLM non disponibile: {e}")

# ============================================================
# 3. API UNIFICATA
# ============================================================

class UnifiedWallet:
    """
    API unificata che combina:
    - Core Rust (identità, asset, storage)
    - Plugin XRP/XLM (transazioni, saldi, derivazione)
    - Futuro: Reticulum
    """
    
    def __init__(self, db_path: str = "wallet.db"):
        self.core = create_core(db_path)
        self._xrp_manager: Optional[HybridXRPManager] = None
        self._initialized = False
        self.logger = logging.getLogger(__name__)
    
    # ============================================================
    # INIZIALIZZAZIONE
    # ============================================================
    
    def init_xrp(self, data_file: str = "xrp_data.json", network: str = "testnet", crypto: str = "XRP"):
        if not PLUGIN_XRP_AVAILABLE:
            raise ImportError("Plugin XRP/XLM non disponibile")
        
        if self._xrp_manager is None:
            if crypto is None or crypto.lower() == "auto":
                crypto = "XRP"
            self._xrp_manager = wm.create_manager(
                data_file=data_file,
                crypto_type=crypto,
                network=network
            )
            self._initialized = True
            self.logger.info(f"✅ Manager {crypto} inizializzato su {network}")
        return self._xrp_manager
    
    def init_xlm(self, data_file: str = "xlm_data.json", network: str = "testnet"):
        return self.init_xrp(data_file, network, "XLM")
    
    # ============================================================
    # IDENTITA'
    # ============================================================
    
    def create_wallet(self, name: str = None, crypto_type: str = "XRP", strength: int = 256, passphrase: str = "") -> Dict[str, Any]:
        """Crea un nuovo wallet con strength (128=12 parole, 256=24 parole) e passphrase opzionale"""
        identity_id = self.core.create_identity(name)
        
        if not self._xrp_manager:
            self.init_xrp(crypto=crypto_type)
        
        if crypto_type == "XRP":
            # 🔥 PASSA PASSPHRASE
            wallet_data = self._xrp_manager.create_new_wallet_bip39(passphrase=passphrase, strength=strength)
            self._xrp_manager.save()
        elif crypto_type == "XLM":
            self._xrp_manager.set_crypto("XLM")
            # 🔥 PASSA PASSPHRASE (se supportata da Stellar)
            wallet_data = self._xrp_manager.create_new_wallet_stellar(passphrase=passphrase, strength=strength)
            self._xrp_manager.save()
        else:
            raise ValueError(f"Crypto non supportata: {crypto_type}")
        
        return {
            "identity_id": identity_id,
            "crypto_type": crypto_type,
            "address": wallet_data.get("first_address"),
            "mnemonic": wallet_data.get("seed_phrase"),
            "word_count": len(wallet_data.get("seed_phrase", "").split()),
            "seed": wallet_data.get("first_seed_xrp") or wallet_data.get("first_seed_stellar"),
            "passphrase": passphrase if passphrase else None,
            "wallet_data": wallet_data
        }
    
    def import_wallet(self, seed_input: Union[str, List[str]], 
                      name: str = None,
                      crypto_type: str = "auto",
                      passphrase: str = "") -> Dict[str, Any]:
        """Importa un wallet con passphrase opzionale"""
        identity_id = self.core.create_identity(name)
        
        if not self._xrp_manager:
            self.init_xrp(crypto="XRP")
        
        if crypto_type is None or crypto_type.lower() == "auto":
            detected_type = self._xrp_manager.detect_input_type(seed_input)
            if detected_type == "stellar_seed":
                self._xrp_manager.set_crypto("XLM")
            else:
                self._xrp_manager.set_crypto("XRP")
        else:
            self._xrp_manager.set_crypto(crypto_type)
        
        # 🔥 PASSA PASSPHRASE ALL'IMPORT
        if passphrase:
            result = self._xrp_manager.import_wallet(seed_input, passphrase=passphrase)
        else:
            result = self._xrp_manager.import_wallet(seed_input)
        self._xrp_manager.save()
        
        return {
            "identity_id": identity_id,
            "crypto_type": self._xrp_manager.crypto_type,
            "address": result.get("first_address"),
            "seed_type": result.get("seed_type"),
            "passphrase": passphrase if passphrase else None,
            "wallet_data": result
        }
    
    # ============================================================
    # TRANSAZIONI
    # ============================================================
    
    def get_balance(self, force_refresh: bool = False) -> float:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        return self._xrp_manager.get_balance(force_refresh)
    
    def send_payment(self, to_address: str, amount: float, 
                     memo_text: str = "") -> Dict[str, Any]:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        return self._xrp_manager.send_payment(to_address, amount, memo_text)
    
    def get_address(self) -> str:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        return self._xrp_manager.get_address()
    
    def derive_addresses(self, keyword: str = "default", count: int = 5) -> List[Dict]:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        
        results = self._xrp_manager.derive_addresses(keyword, count)
        return [r.to_dict() for r in results]
    
    # ============================================================
    # RETE
    # ============================================================
    
    def set_network(self, network: str) -> None:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        self._xrp_manager.set_network(network)
    
    def get_crypto_type(self) -> str:
        if not self._xrp_manager:
            return "XRP"
        return self._xrp_manager.crypto_type
    
    def fund_testnet(self) -> bool:
        if not self._xrp_manager:
            raise ValueError("Wallet non inizializzato")
        return self._xrp_manager.fund_testnet()
    
    # ============================================================
    # PERSISTENZA
    # ============================================================
    
    def save(self):
        if self._xrp_manager:
            self._xrp_manager.save()
    
    def load(self) -> bool:
        if self._xrp_manager:
            return self._xrp_manager.load()
        return False
    
    # ============================================================
    # INFO
    # ============================================================
    
    def get_info(self) -> Dict[str, Any]:
        info = {
            "core": self.core.info(),
            "xrp_initialized": self._xrp_manager is not None,
        }
        
        if self._xrp_manager:
            info["xrp"] = {
                "crypto_type": self._xrp_manager.crypto_type,
                "network": self._xrp_manager.network,
                "address": self._xrp_manager.get_address() if self._xrp_manager.is_loaded() else None,
                "loaded": self._xrp_manager.is_loaded(),
                "seed_type": self._xrp_manager.seed_type,
            }
        
        return info
    
    def get_full_info(self) -> Dict[str, Any]:
        if not self._xrp_manager:
            return {"error": "Wallet non inizializzato"}
        
        manager = self._xrp_manager
        info = {
            "crypto_type": manager.crypto_type,
            "network": manager.network,
            "address": manager.get_address() if manager.is_loaded() else None,
            "loaded": manager.is_loaded(),
            "seed_type": manager.seed_type,
            "balance": None,
        }
        
        if manager.is_loaded():
            try:
                info["balance"] = manager.get_balance()
            except:
                pass
        
        if manager.seed_phrase:
            info["mnemonic"] = manager.seed_phrase
            info["word_count"] = len(manager.seed_phrase.split())
        
        if manager.seed_numbers:
            info["secret_numbers"] = manager.seed_numbers
            info["secret_numbers_formatted"] = " ".join(manager.seed_numbers)
        
        if manager.base_seed_xrp:
            info["xrp_seed"] = manager.base_seed_xrp
        
        if manager.base_seed_stellar:
            info["stellar_seed"] = manager.base_seed_stellar
        
        if manager.base_private:
            info["private_key"] = manager.base_private.hex()
        
        info["derived_wallets"] = [w.to_dict() for w in manager._derived_wallets.values()]
        
        return info

# ============================================================
# 4. FUNZIONI FACTORY
# ============================================================

def create_wallet(db_path: str = "wallet.db", crypto: str = "XRP", network: str = "testnet") -> UnifiedWallet:
    """Crea un'istanza del wallet unificato"""
    wallet = UnifiedWallet(db_path)
    wallet.init_xrp(crypto=crypto, network=network)
    return wallet

def create_xrp_wallet(db_path: str = "wallet.db", network: str = "testnet") -> UnifiedWallet:
    return create_wallet(db_path, "XRP", network)

def create_xlm_wallet(db_path: str = "wallet.db", network: str = "testnet") -> UnifiedWallet:
    return create_wallet(db_path, "XLM", network)

# ============================================================
# 5. TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST WALLET API")
    print("=" * 60)
    
    # Test XRP
    print("\n📤 Test XRP...")
    wallet_xrp = create_xrp_wallet("test_xrp.db")
    result = wallet_xrp.create_wallet("Marco", "XRP")
    print(f"   Address XRP: {result['address']}")
    
    # Test XLM
    print("\n📤 Test XLM...")
    wallet_xlm = create_xlm_wallet("test_xlm.db")
    result = wallet_xlm.create_wallet("Marco", "XLM")
    print(f"   Address XLM: {result['address']}")
    
    print("\n✅ Test completato!")