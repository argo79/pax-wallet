#!/usr/bin/env python3
"""
utils/helpers.py - Funzioni di utilità per il CLI
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_active_wallet_name(active_wallet_name_file: Path) -> Optional[str]:
    if active_wallet_name_file.exists():
        try:
            with open(active_wallet_name_file, 'r') as f:
                name = f.read().strip()
                if name:
                    return name
        except:
            pass
    return None


def get_wallet_display(active_wallet_name_file: Path) -> str:
    name = get_active_wallet_name(active_wallet_name_file)
    return name if name else "nessun wallet"


def ensure_wallet_settings(cli_instance) -> bool:
    """
    Legge il wallet attivo e imposta network e crypto di conseguenza.
    USA DIRECTLY wallet._xrp_manager
    """
    wallet_name = get_active_wallet_name(cli_instance.active_wallet_name_file)
    if not wallet_name:
        return False

    wallet_file = cli_instance.wallets_dir / f"{wallet_name}.json"
    if not wallet_file.exists():
        return False

    try:
        with open(wallet_file, 'r') as f:
            data = json.load(f)

        saved_network = data.get("network", "testnet")
        saved_crypto = data.get("crypto_type", "XRP")

        # 🔥 USA DIRETTAMENTE wallet._xrp_manager
        if cli_instance.wallet and cli_instance.wallet._xrp_manager:
            manager = cli_instance.wallet._xrp_manager
            
            if saved_network != manager.network:
                manager.set_network(saved_network)
                logger.info(f"🌐 Rete impostata: {saved_network.upper()}")
            
            if saved_crypto != manager.crypto_type:
                manager.set_crypto(saved_crypto)
                logger.info(f"🪙 Crypto impostata: {saved_crypto}")
            
            # Carica i dati se necessario
            if not manager.is_loaded():
                manager.seed_type = data.get("seed_type")
                manager.seed_phrase = data.get("seed_phrase")
                manager.seed_numbers = data.get("seed_numbers")
                manager.passphrase = data.get("passphrase", "")
                
                base_private_hex = data.get("base_private")
                if base_private_hex:
                    manager.base_private = bytes.fromhex(base_private_hex)
                
                manager.base_seed_xrp = data.get("base_seed_xrp")
                manager.base_seed_stellar = data.get("base_seed_stellar")
                manager._correct_address = data.get("current_address")
                manager.crypto_type = saved_crypto
                manager.network = saved_network
                
                # Carica wallet derivati
                manager._derived_wallets = {}
                for w_data in data.get("derived_wallets", []):
                    try:
                        from wallet_manager import WalletInfo
                        info = WalletInfo.from_dict(w_data)
                        manager._derived_wallets[f"{info.keyword}:{info.index}"] = info
                    except:
                        pass
                
                logger.info(f"✅ Wallet caricato: {wallet_name}")
            
            return True
        else:
            logger.warning("Wallet non inizializzato")
            return False

    except Exception as e:
        logger.error(f"Errore: {e}")
        return False


def save_address_to_wallet(cli_instance, name: str, address: str) -> bool:
    if not name:
        return False
    
    target = cli_instance.wallets_dir / f"{name}.json"
    if not target.exists():
        return False
    
    try:
        with open(target, 'r') as f:
            data = json.load(f)
        data["current_address"] = address
        with open(target, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except:
        return False


def format_address(address: str, length: int = 8) -> str:
    if len(address) <= length * 2:
        return address
    return f"{address[:length]}...{address[-length:]}"


def validate_xrp_address(address: str) -> bool:
    return address.startswith('r') and len(address) >= 25


def validate_xlm_address(address: str) -> bool:
    return address.startswith('G') and len(address) >= 56


def get_network_display(network: str) -> str:
    display = {"mainnet": "MAINNET", "testnet": "TESTNET", "devnet": "DEVNET"}
    return display.get(network, network.upper())