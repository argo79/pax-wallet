#!/usr/bin/env python3
"""
wallet_cli.py - CLI per wallet XRP/XLM con supporto multi-wallet, trustline, token e Reticulum
"""

import sys
import json
import re
import logging
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
import threading

# ============================================================
# VERSIONE
# ============================================================
VERSION = "0.9.1b"
__version__ = VERSION


# ============================================================
# PATCH PER RETICULUM - DEVE ESSERE PRIMA DI TUTTO!
# ============================================================
import RNS
try:
    from RNS.Interfaces import Interface
except ImportError:
    class Interface:
        pass
    setattr(RNS, 'Interface', Interface)
    if not hasattr(RNS, 'Interfaces'):
        class Interfaces:
            pass
        RNS.Interfaces = Interfaces
    setattr(RNS.Interfaces, 'Interface', Interface)

from core_wrapper import create_core, CoreWallet, get_core_path
from wallet_api import create_wallet, UnifiedWallet

import colorama
colorama.init()

# ============================================================
# IMPORT COMANDI XLM
# ============================================================

try:
    from commands.xlm_commands import send_xlm, history_xlm, info_xlm, faucet_xlm
    XLM_AVAILABLE = True
except ImportError as e:
    XLM_AVAILABLE = False
    def send_xlm(cli):
        print("❌ Comando XLM non disponibile. Installa stellar-sdk")
    def history_xlm(cli):
        print("❌ Comando XLM non disponibile. Installa stellar-sdk")
    def info_xlm(cli):
        print("❌ Comando XLM non disponibile. Installa stellar-sdk")
    def faucet_xlm(cli):
        print("❌ Comando XLM non disponibile. Installa stellar-sdk")


# ============================================================
# IMPORT RETICULUM MANAGER
# ============================================================

try:
    from reticulum.reticulum_manager import ReticulumManager, ReticulumConfig
    RETICULUM_AVAILABLE = True
except ImportError as e:
    RETICULUM_AVAILABLE = False
    print(f"⚠️ Reticulum non disponibile: {e}")


# ============================================================
# IMPORT METRICHE
# ============================================================

try:
    from reticulum.gateway_metrics import GatewayMetrics
    METRICS_AVAILABLE = True
except ImportError as e:
    METRICS_AVAILABLE = False
    print(f"⚠️ Metriche non disponibili: {e}")


# ============================================================
# 2. COLORI PER OUTPUT
# ============================================================

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_green(msg): print(f"{Colors.GREEN}{msg}{Colors.RESET}")
def print_yellow(msg): print(f"{Colors.YELLOW}{msg}{Colors.RESET}")
def print_blue(msg): print(f"{Colors.BLUE}{msg}{Colors.RESET}")
def print_red(msg): print(f"{Colors.RED}{msg}{Colors.RESET}")
def print_cyan(msg): print(f"{Colors.CYAN}{msg}{Colors.RESET}")
def print_bold(msg): print(f"{Colors.BOLD}{msg}{Colors.RESET}")


# ============================================================
# 3. WALLET CLI
# ============================================================

class WalletCLI:
    def __init__(self):
        self.wallet: Optional[UnifiedWallet] = None
        self.data_file = "wallet_cli.db"
        self.wallets_dir = Path("wallets")
        self.wallets_dir.mkdir(exist_ok=True)
        self.active_wallet_name_file = Path("active_wallet.txt")
        self.rubrica_file = Path("rubrica.json")
        self._interactive_mode = False
        
        # ============================================================
        # RETICULUM - SINGLETON PER TUTTA LA SESSIONE
        # ============================================================
        self.reticulum: Optional[ReticulumManager] = None
        self.reticulum_initialized = False
        self.reticulum_config = ReticulumConfig()
        self.metrics = None

        # Inizializza Reticulum all'avvio della CLI (una volta sola)
        if RETICULUM_AVAILABLE:
            self._init_reticulum()

    def _validate_wallet_name(self, name: str) -> bool:
        """Verifica che il nome del wallet sia sicuro (solo caratteri validi)"""
        if not name:
            print_red("❌ Nome wallet vuoto")
            return False
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            print_red(f"❌ Nome wallet non valido: {name}")
            print_yellow("   Usa solo lettere, numeri, underscore (_) e trattini (-)")
            return False
        return True

    def _init_reticulum(self):
        """Inizializza Reticulum UNA SOLA VOLTA all'avvio della CLI"""
        if not RETICULUM_AVAILABLE:
            return
        
        if not self.reticulum_initialized:
            # 1. CREA RETICULUM MANAGER
            self.reticulum = ReticulumManager()
            
            # 2. CREA METRICS E IMPOSTA NEL MANAGER (PRIMA DI init!)
            if METRICS_AVAILABLE:
                try:
                    self.metrics = GatewayMetrics(self.reticulum.identity)
                    self.metrics.set_my_gateway_id(self.reticulum.gateway_address)
                    
                    # ============================================================
                    # 🔥 IMPOSTA use_internet DAL CONFIG!
                    # ============================================================
                    if hasattr(self.reticulum, 'config'):
                        self.metrics.set_use_internet(self.reticulum.config.use_internet)
                        self.metrics.set_ledger_timeout(self.reticulum.config.ledger_timeout_seconds)
                        self.metrics.set_ledger_check_interval(self.reticulum.config.ledger_check_interval)
                    
                    # 🔥 IMPOSTA METRICS NEL MANAGER (PRIMA DI init!)
                    self.reticulum.set_metrics(self.metrics)
                    print_green("📡 Metrics create e collegate")
                except Exception as e:
                    print_yellow(f"⚠️ Errore avvio metriche: {e}")
                    self.metrics = None
            
            # 3. ORA init() TROVERÀ metrics NON None
            self.reticulum.init()
            self.reticulum_initialized = True
            
            # Avvia query loop
            if METRICS_AVAILABLE and self.metrics:
                try:
                    self.metrics.start_query_loop(
                        interval=3600,
                        max_peers=10,
                        max_hops=3
                    )
                    print_green("📡 Metriche gateway avviate")
                except Exception as e:
                    print_yellow(f"⚠️ Errore avvio query loop: {e}")
            else:
                print_yellow("⚠️ Metrics non disponibili, alcune funzioni Reticulum potrebbero non funzionare")
            
            status = self.reticulum.get_status()
            print_green("📡 Reticulum attivo per tutta la sessione")
            print_yellow(f"   Gateway Hash: {status.get('gateway_address', 'N/A')}")
            print_yellow(f"   Wallet Hash:  {status.get('wallet_address', 'N/A')}")
            if self.metrics:
                print_green(f"   Metrics: ✅ Disponibili")
            else:
                print_red(f"   Metrics: ❌ NON DISPONIBILI")

    def init(self, network: str = None):
        """Inizializza il wallet"""
        active = self._get_active_wallet_name()
        
        if active:
            wallet_file = self.wallets_dir / f"{active}.json"
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        data = json.load(f)
                        network = data.get("network", "testnet")
                        crypto = data.get("crypto_type", "XRP")
                except:
                    network = "testnet"
                    crypto = "XRP"
            else:
                network = "testnet"
                crypto = "XRP"
        else:
            network = "testnet"
            crypto = "XRP"
        
        self.wallet = create_wallet(self.data_file)
        self.wallet.init_xrp(network=network, crypto=crypto)
        
        # 🔥 CARICA IL WALLET SALVATO
        loaded = self.wallet._xrp_manager.load()
        if loaded:
            network = self.wallet._xrp_manager.network
            crypto = self.wallet._xrp_manager.crypto_type
        
        if self.wallet._xrp_manager:
            self.wallet._xrp_manager.set_network(network)
            self.wallet._xrp_manager.set_crypto(crypto)
        
        print_green(f"✅ Wallet: {active or 'nuovo'} | Rete: {network.upper()} | Crypto: {crypto}")
        return self.wallet
    
    def _get_active_wallet_name(self) -> str:
        if self.active_wallet_name_file.exists():
            return self.active_wallet_name_file.read_text().strip()
        return ""
    
    def _set_active_wallet_name(self, name: str) -> None:
        if not self._validate_wallet_name(name):
            return
        with open(self.active_wallet_name_file, "w") as f:
            f.write(name)
    
    def _get_wallet_list(self) -> List[Dict]:
        wallets = []
        for file in self.wallets_dir.glob("*.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                    address = data.get("current_address", "unknown")
                    if address == "unknown":
                        derived = data.get("derived_wallets", [])
                        if derived:
                            address = derived[0].get("address", "unknown")
                    
                    wallets.append({
                        "name": file.stem,
                        "address": address,
                        "address_short": address[:8] + "..." if address != "unknown" else "❌",
                        "crypto": data.get("crypto_type", "XRP"),
                        "network": data.get("network", "testnet"),
                    })
            except Exception as e:
                pass
        return wallets
    
    def _get_contatti(self) -> List[Dict]:
        if not self.rubrica_file.exists():
            return []
        try:
            with open(self.rubrica_file) as f:
                data = json.load(f)
                return data.get("contatti", [])
        except:
            return []
    
    def _cerca_contatto(self, nome: str) -> Optional[Dict]:
        contatti = self._get_contatti()
        for c in contatti:
            if c.get("nome", "").lower() == nome.lower():
                return c
        return None
    
    def _save_wallet_as(self, name: str) -> bool:
        if not self.wallet or not self.wallet._xrp_manager:
            return False
        
        if not self._validate_wallet_name(name):
            return False
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            return False
        
        dest = self.wallets_dir / f"{name}.json"
        
        # Path traversal protection
        try:
            dest.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Percorso non valido: {dest}")
            return False
        
        correct_address = manager._correct_address
        if not correct_address:
            try:
                correct_address = manager.get_address("default", 0)
            except:
                correct_address = None
        
        data = {
            "seed_type": manager.seed_type,
            "seed_phrase": manager.seed_phrase,
            "seed_numbers": manager.seed_numbers,
            "passphrase": manager.passphrase,
            "base_private": manager.base_private.hex() if manager.base_private else None,
            "base_seed_xrp": manager.base_seed_xrp,
            "base_seed_stellar": manager.base_seed_stellar,
            "current_address": correct_address,
            "network": manager.network,
            "crypto_type": manager.crypto_type,
            "created_at": datetime.now().isoformat(),
            "derived_wallets": [info.to_dict() for info in manager._derived_wallets.values()]
        }
        
        with open(dest, 'w') as f:
            json.dump(data, f, indent=2)
        
        print_green(f"✅ Wallet '{name}' salvato con indirizzo: {correct_address}")
        print_yellow(f"🌐 Rete salvata: {manager.network.upper()}")
        print_yellow(f"🪙 Crypto salvata: {manager.crypto_type}")
        return True
    
    def _switch_wallet(self, name: str) -> bool:
        """Cambia il wallet attivo con quello specificato"""
        # VALIDA IL NOME PRIMA DI USARLO
        if not self._validate_wallet_name(name):
            return False
        
        source = self.wallets_dir / f"{name}.json"
        
        # Path traversal protection
        try:
            source.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Percorso non valido: {source}")
            return False
        
        if not source.exists():
            return False
        
        try:
            with open(source, 'r') as f:
                wallet_data = json.load(f)
            
            manager = self.wallet._xrp_manager
            
            saved_network = wallet_data.get("network", "testnet")
            saved_crypto = wallet_data.get("crypto_type", "XRP")
            
            manager.seed_type = wallet_data.get("seed_type")
            manager.seed_phrase = wallet_data.get("seed_phrase")
            manager.seed_numbers = wallet_data.get("seed_numbers")
            manager.passphrase = wallet_data.get("passphrase", "")
            manager.base_seed_xrp = wallet_data.get("base_seed_xrp")
            manager.base_seed_stellar = wallet_data.get("base_seed_stellar")
            manager._correct_address = wallet_data.get("current_address")
            manager.crypto_type = saved_crypto
            manager.network = saved_network
            
            base_private_hex = wallet_data.get("base_private")
            if base_private_hex:
                manager.base_private = bytes.fromhex(base_private_hex)
            
            manager._derived_wallets = {}
            for w_data in wallet_data.get("derived_wallets", []):
                try:
                    from wallet_manager import WalletInfo
                    info = WalletInfo.from_dict(w_data)
                    manager._derived_wallets[f"{info.keyword}:{info.index}"] = info
                except:
                    pass
            
            self._set_active_wallet_name(name)
            
            print_green(f"✅ Wallet cambiato a: {name}")
            print_yellow(f"🌐 Rete: {saved_network.upper()}")
            print_yellow(f"🪙 Crypto: {saved_crypto}")
            return True
            
        except Exception as e:
            print_red(f"❌ Errore nel cambio wallet: {e}")
            return False

    def _get_wallet_network(self) -> str:
        active = self._get_active_wallet_name()
        if active:
            wallet_file = self.wallets_dir / f"{active}.json"
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        data = json.load(f)
                        return data.get("network", "testnet")
                except:
                    pass
        return "testnet"
    
    def _ensure_correct_network(self):
        if not self.wallet or not self.wallet._xrp_manager:
            return
        
        manager = self.wallet._xrp_manager
        active = self._get_active_wallet_name()
        
        if active:
            wallet_file = self.wallets_dir / f"{active}.json"
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        data = json.load(f)
                        saved_network = data.get("network", "testnet")
                        saved_crypto = data.get("crypto_type", "XRP")
                        
                        if saved_network != manager.network:
                            manager.set_network(saved_network)
                            print_yellow(f"🌐 Rete impostata a: {saved_network.upper()}")
                        
                        if saved_crypto != manager.crypto_type:
                            manager.set_crypto(saved_crypto)
                            print_yellow(f"🪙 Crypto impostata a: {saved_crypto}")
                except:
                    pass
    
    # ============================================================
    # PARSE TX DATE - DAL VECCHIO CODICE
    # ============================================================
    
    def _parse_tx_date(self, tx: Dict, tx_data: Dict) -> str:
        from datetime import datetime
        
        date_str = ""
        try:
            if "date" in tx:
                ledger_time = tx.get("date", 0)
                if ledger_time:
                    date_obj = datetime.fromtimestamp(ledger_time + 946684800)
                    date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        
        if not date_str and "close_time_iso" in tx_data:
            try:
                close_time = tx_data.get("close_time_iso", "")
                if close_time:
                    date_str = close_time.replace("T", " ").replace("Z", "")[:19]
            except:
                pass
        
        return date_str
    
    # ============================================================
    # FORMAT TIME AGO - PER TEMPI RELATIVI
    # ============================================================
    
    def _format_time_ago(self, timestamp: int) -> str:
        """Formatta il timestamp in 'X minuti fa', 'X ore fa', ecc."""
        if not timestamp:
            return "Mai"
        
        now = int(time.time())
        diff = now - timestamp
        
        if diff < 60:
            return "Poco fa"
        elif diff < 3600:
            mins = diff // 60
            return f"{mins} min fa" if mins > 1 else "1 min fa"
        elif diff < 86400:
            hours = diff // 3600
            return f"{hours} ore fa" if hours > 1 else "1 ora fa"
        elif diff < 604800:
            days = diff // 86400
            return f"{days} giorni fa" if days > 1 else "1 giorno fa"
        else:
            weeks = diff // 604800
            return f"{weeks} sett fa" if weeks > 1 else "1 sett fa"
    
    # ============================================================
    # PRINT TRANSACTIONS - DAL VECCHIO CODICE
    # ============================================================
    
    def _print_transactions(self, transactions: List, address: str) -> None:
        from datetime import datetime
        import base64
        
        manager = self.wallet._xrp_manager if self.wallet else None
        
        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────┬──────────────────────────────────────────────────┬────────────────────┐")
        print(f"│ #  │ Data/Ora            │ Tipo       │ Importo          │ Fee        │ Da/A                                              │ Memo               │")
        print("├────┼─────────────────────┼────────────┼──────────────────┼────────────┼──────────────────────────────────────────────────┼────────────────────┤")
        
        for idx, tx_data in enumerate(transactions, 1):
            tx = tx_data.get("tx_json", {})
            if not tx:
                continue
            
            tx_type = tx.get("TransactionType", "Unknown")
            date_str = self._parse_tx_date(tx, tx_data)
            
            fee_drops = tx.get("Fee", "0")
            try:
                fee_xrp = int(fee_drops) / 1_000_000
                fee_str = f"{fee_xrp:.6f}".rstrip('0').rstrip('.')
                if '.' in fee_str:
                    fee_str = fee_str[:10]
                if fee_str == "":
                    fee_str = "0"
            except:
                fee_str = fee_drops
            
            if tx_type == "Payment":
                amount = tx.get("Amount", tx.get("DeliverMax", "0"))
                
                if isinstance(amount, dict):
                    token_value = amount.get('value', '0')
                    token_currency = amount.get('currency', '???')
                    
                    if manager and len(token_currency) > 3:
                        decoded = manager._decode_currency_hex(token_currency)
                        if decoded and decoded != token_currency:
                            token_currency = decoded
                    
                    try:
                        val_float = float(token_value)
                        amount_str = f"{val_float:.6f}".rstrip('0').rstrip('.')
                        if not amount_str:
                            amount_str = "0"
                        amount_str += f" {token_currency}"
                    except:
                        amount_str = f"{token_value[:8]} {token_currency}"
                else:
                    try:
                        amount_xrp = int(amount) / 1_000_000
                        amount_str = f"{amount_xrp:.6f}".rstrip('0').rstrip('.')
                        if not amount_str:
                            amount_str = "0"
                        amount_str += " XRP"
                    except:
                        amount_str = f"{amount} drops"
                
                sender = tx.get("Account", "unknown")
                destination = tx.get("Destination", "unknown")
                
                if destination == address:
                    direction = "RICEVUTO"
                    da_a = f"Da: {sender}"
                elif sender == address:
                    direction = "INVIATO"
                    da_a = f"A: {destination}"
                else:
                    direction = "ALTRO"
                    da_a = f"{sender} → {destination}"
                
                memo_display = ""
                memos = tx.get("Memos", [])
                if memos:
                    try:
                        memo_dict = memos[0].get("Memo", {})
                        memo_data = memo_dict.get("MemoData", "")
                        if memo_data:
                            memo_text = ""
                            try:
                                memo_bytes = bytes.fromhex(memo_data)
                                memo_text = memo_bytes.decode('utf-8', errors='ignore')
                            except:
                                try:
                                    while len(memo_data) % 4 != 0:
                                        memo_data += '='
                                    memo_bytes = base64.b64decode(memo_data)
                                    memo_text = memo_bytes.decode('utf-8', errors='ignore')
                                except:
                                    memo_text = memo_data[:20]
                            
                            if memo_text:
                                memo_clean = ''.join(c for c in memo_text if c.isprintable() or c == ' ')
                                if memo_clean.strip():
                                    memo_display = memo_clean[:256]
                    except:
                        pass
                
                if len(da_a) > 48:
                    da_a_display = da_a[:45] + "..."
                else:
                    da_a_display = da_a
                
                if len(memo_display) > 18:
                    memo_display = memo_display[:15] + "..."
                
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {direction:<10} │ {amount_str:<16} │ {fee_str:<10} │ {da_a_display:<48} │ {memo_display:<18} │")
            else:
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {tx_type:<10} │ {'':<16} │ {fee_str:<10} │ {'':<48} │ {'':<18} │")
        
        print("└────┴─────────────────────┴────────────┴──────────────────┴────────────┴──────────────────────────────────────────────────┴────────────────────┘")
        print(f"Totale: {len(transactions)} transazioni mostrate")


    

    # ============================================================
    # 4. COMANDI PRINCIPALI
    # ============================================================
    
    def cmd_create(self, name: str = "default", crypto: str = "XRP", network: str = "testnet"):
        if not self.wallet:
            self.init(network)
        
        if not self._validate_wallet_name(name):
            return None
        
        print_blue(f"📤 Creazione wallet {crypto} su {network.upper()}...")
        
        manager = self.wallet._xrp_manager
        if network != manager.network:
            manager.set_network(network)
            print_yellow(f"🌐 Rete impostata a: {network.upper()}")
        
        strength = 256
        if crypto == "XRP":
            strength = 128
        
        result = self.wallet.create_wallet(name, crypto, strength=strength)
        
        print_green(f"\n✅ Wallet creato su {network.upper()}!")
        print(f"   Identity: {result['identity_id']}")
        print(f"   Address: {result['address']}")
        print(f"   Mnemonic: {result['mnemonic']}")
        print(f"   Word Count: {result['word_count']}")
        print(f"   Seed: {result.get('seed', 'N/A')}")
        self.wallet.save()
        
        self._save_wallet_as(name)
        self._set_active_wallet_name(name)
        
        return result
    
    def cmd_import(self, seed_input: str, name: str = "imported", crypto: str = "auto", network: str = "testnet"):
        if not self.wallet:
            self.init(network)
        
        if not self._validate_wallet_name(name):
            return None
        
        print_blue(f"📥 Importazione wallet...")
        
        manager = self.wallet._xrp_manager
        
        if network != manager.network:
            manager.set_network(network)
            print_yellow(f"🌐 Rete impostata a: {network.upper()}")
        
        cleaned = seed_input
        cleaned = re.sub(r'[A-Ha-h]:', '', cleaned)
        cleaned = re.sub(r',', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        numbers_parts = cleaned.split()
        
        import_type = manager.detect_input_type(seed_input)
        print(f"   Tipo rilevato: {import_type}")
        
        crypto_param = None
        if crypto and crypto.lower() != "auto":
            crypto_param = crypto
        
        if len(numbers_parts) == 8 and all(p.isdigit() and len(p) == 6 for p in numbers_parts):
            import_type = "numbers"
            print_cyan(f"   🔢 Numeri Xaman rilevati: {numbers_parts}")
            print_cyan("   🔄 Conversione numeri Xaman via Node.js...")
            result = self.wallet.import_wallet(" ".join(numbers_parts), name, crypto_param)
        else:
            result = self.wallet.import_wallet(seed_input, name, crypto_param)
        
        print_green(f"\n✅ Wallet importato!")
        print(f"   Identity: {result['identity_id']}")
        print(f"   Address: {result['address']}")
        print(f"   Type: {result['seed_type']}")
        
        print(f"\n📊 DETTAGLI WALLET:")
        print(f"   Crypto: {manager.crypto_type}")
        print(f"   Network: {manager.network}")
        
        if manager.seed_phrase:
            print(f"   Mnemonic: {manager.seed_phrase}")
            print(f"   Word Count: {len(manager.seed_phrase.split())}")
        
        if manager.seed_numbers:
            print(f"   Secret Numbers: {' '.join(manager.seed_numbers)}")
        
        if manager.base_seed_xrp:
            print(f"   XRP Seed: {manager.base_seed_xrp}")
        
        if manager.base_seed_stellar:
            print(f"   Stellar Seed: {manager.base_seed_stellar}")
        
        if manager.base_private:
            print(f"   Private Key: {manager.base_private.hex()}")
        
        try:
            balance = manager.get_balance()
            print(f"   Saldo: {balance} {manager.crypto_type}")
        except:
            pass
        
        self.wallet.save()
        self._save_wallet_as(name)
        self._set_active_wallet_name(name)
        
        return result
    
    def _cmd_balance_xlm(self, refresh: bool = False):
        manager = self.wallet._xrp_manager
        try:
            balance = manager.get_balance(refresh)
            print_green(f"   Saldo: {balance:.7f} XLM")
            return balance
        except Exception as e:
            print_red(f"   ❌ Errore: {e}")
            return None
    
    def cmd_balance(self, refresh: bool = False):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return self._cmd_balance_xlm(refresh)
        
        print_blue(f"💰 Recupero saldo XRP su {manager.network.upper()}...")
        
        try:
            balance = manager.get_balance(refresh)
            print_green(f"   Saldo: {balance:.6f} XRP")
            return balance
        except Exception as e:
            print_red(f"   ❌ Errore: {e}")
            return None
    
    def cmd_address(self):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        address = self.wallet.get_address()
        print_green(f"   Address: {address}")
        return address
    
    def cmd_derive(self, keyword: str = "default", count: int = 5):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        crypto_type = self.wallet._xrp_manager.crypto_type
        
        # 🔥 PER STELLAR: MOSTRA SOLO L'INDIRIZZO
        if crypto_type == "XLM":
            try:
                address = self.wallet.get_address()
                print_green(f"📤 Indirizzo Stellar: {address}")
            except Exception as e:
                print_red(f"❌ Errore: {e}")
            return
        
        # PER XRP: derivazione multipla
        print_blue(f"📤 Derivazione {count} indirizzi XRP (keyword: {keyword})...")
        
        try:
            addresses = self.wallet.derive_addresses(keyword, count)
            for i, addr in enumerate(addresses):
                print(f"   {i}: {addr['address']}")
        except ValueError as e:
            print_red(f"❌ {e}")
        
        return addresses
    
    def cmd_info(self):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        info = manager.get_seed_info()
        
        print_bold("\n📊 INFO COMPLETA WALLET")
        print("=" * 60)
        print(f"   Crypto: {manager.crypto_type}")
        print(f"   Network: {manager.network.upper()}")
        print(f"   Address: {manager.get_address()}")
        print(f"   Seed Type: {manager.seed_type}")
        
        if info.get('balance') is not None:
            print(f"   Balance: {info['balance']:.6f} {manager.crypto_type}")
        
        if info.get('seed_phrase'):
            print(f"\n   Mnemonic: {info['seed_phrase']}")
            print(f"   Word Count: {info.get('word_count', 0)}")
        
        if info.get('secret_numbers'):
            print(f"\n   Secret Numbers: {info.get('formatted')}")
        
        if info.get('seed_xrp'):
            print(f"\n   XRP Seed: {info['seed_xrp']}")
        
        if info.get('private_key'):
            print(f"\n   Private Key: {info['private_key']}")
        
        derived = manager.list_derived()
        if derived:
            print(f"\n   Derived Wallets: {len(derived)}")
            for w in derived[:5]:
                print(f"      - {w.address} ({w.keyword}:{w.index})")
        
        print("=" * 60)
    
    # ============================================================
    # HISTORY - COPIA DAL VECCHIO CODICE
    # ============================================================
    
    def cmd_history(self, limit: int = 10):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            history_xlm(self, ["--limit", str(limit)])
            return
        
        address = manager.get_address()
        network = manager.network
        
        print(f"\n📜 STORICO TRANSAZIONI XRP ({network.upper()})")
        print("=" * 80)
        print(f"Indirizzo: {address}")
        print(f"Limite:    {limit} transazioni")
        print("=" * 80)
        
        try:
            from xrpl.models.requests import AccountTx
            from xrpl.models.response import ResponseStatus
            from xrpl.clients import JsonRpcClient
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/",
                "devnet": "https://s.devnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(network, urls["testnet"]))
            
            request = AccountTx(
                account=address,
                ledger_index_min=-1,
                ledger_index_max=-1,
                limit=limit,
                forward=False
            )
            
            print("🔄 Richiesta al ledger...")
            response = client.request(request)
            
            if response.status != ResponseStatus.SUCCESS:
                print(f"❌ Errore: {response.status}")
                return
            
            result = response.result
            transactions = result.get("transactions", [])
            
            if not transactions:
                print("❌ Nessuna transazione trovata.")
                return
            
            self._print_transactions(transactions, address)
            
            if network == "mainnet":
                explorer = f"https://xrpscan.com/account/{address}"
            elif network == "testnet":
                explorer = f"https://testnet.xrpl.org/accounts/{address}"
            else:
                explorer = f"https://devnet.xrpl.org/accounts/{address}"
            print(f"\n🔗 Visualizza tutto: {explorer}")
            
        except Exception as e:
            print_red(f"   ❌ Errore: {e}")
            if network == "mainnet":
                explorer = f"https://xrpscan.com/account/{address}"
            elif network == "testnet":
                explorer = f"https://testnet.xrpl.org/accounts/{address}"
            else:
                explorer = f"https://devnet.xrpl.org/accounts/{address}"
            print(f"\n🔗 Visualizza su: {explorer}")
    
    # ============================================================
    # 4. COMANDI PRINCIPALI 
    # ============================================================

    def cmd_send(self, to_address: str, amount: float, memo: str = ""):
        """Invia pagamento XRP o XLM con conferma"""
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # Gestione XLM
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return self._send_xlm(to_address, amount, memo)
        
        # Gestione XRP
        return self._send_xrp(to_address, amount, memo)

    def _send_xlm(self, to_address: str, amount: float, memo: str = ""):
        """Invia XLM con riepilogo e conferma"""
        # Mostra riepilogo
        if not self._confirm_transaction("XLM", to_address, amount, memo):
            return None
        
        print_blue("📡 Invio in corso...")
        
        args = [to_address, str(amount)]
        if memo:
            args.append(memo)
        
        send_xlm(self, args)
        return True

    def _send_xrp(self, to_address: str, amount: float, memo: str = ""):
        """Invia XRP con riepilogo e conferma"""
        # Mostra riepilogo
        if not self._confirm_transaction("XRP", to_address, amount, memo):
            return None
        
        print_blue("📡 Invio in corso...")
        
        try:
            from xrpl.account import get_balance
            from xrpl.models.transactions import Payment
            from xrpl.transaction import autofill, sign, submit_and_wait
            from xrpl.clients import JsonRpcClient
            from xrpl.wallet import Wallet
            from xrpl.models.transactions import Memo
            
            manager = self.wallet._xrp_manager
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/",
                "devnet": "https://s.devnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(manager.network, urls["testnet"]))
            
            wallet = manager.get_wallet("default", 0)
            source_address = wallet.classic_address
            
            # Controlla saldo
            balance_drops = get_balance(source_address, client)
            balance_xrp = balance_drops / 1_000_000
            
            if balance_xrp < amount:
                print_red(f"   ❌ Saldo insufficiente! Hai: {balance_xrp:.6f} XRP")
                return None
            
            amount_drops = str(int(amount * 1_000_000))
            
            payment_params = {
                "account": source_address,
                "amount": amount_drops,
                "destination": to_address,
            }
            
            # Aggiungi memo se presente
            if memo:
                memo_hex = self._encode_memo_hex(memo)
                payment_params["memos"] = [Memo(memo_data=memo_hex)]
            
            payment = Payment(**payment_params)
            tx = autofill(payment, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)
            
            tx_hash = response.result.get("hash", "unknown")
            
            print_green(f"   ✅ Pagamento inviato!")
            print(f"   Hash: {tx_hash}")
            
            new_balance = get_balance(source_address, client) / 1_000_000
            print(f"   Nuovo saldo: {new_balance:.6f} XRP")
            
            return tx_hash
            
        except Exception as e:
            print_red(f"   ❌ Errore: {e}")
            return None

    def _confirm_transaction(self, crypto: str, to_address: str, amount: float, memo: str = "") -> bool:
        """Mostra il riepilogo e chiede conferma"""
        manager = self.wallet._xrp_manager
        
        print_bold(f"\n📤 INVIO {crypto}")
        print("=" * 60)
        print(f"   Wallet:    {self._get_active_wallet_name()}")
        print(f"   Da:        {manager.get_address()}")
        print(f"   A:         {to_address}")
        print(f"   Importo:   {amount} {crypto}")
        if memo:
            print(f"   📝 Memo:    {memo}")
        print("=" * 60)
        print("")
        
        confirm = input("   Confermi l'invio? (s/n): ")
        if confirm.lower() != 's':
            print_red("❌ Transazione annullata.")
            return False
        
        return True

    def _encode_memo_hex(self, memo: str) -> str:
        """Codifica il memo in hex"""
        memo_hex = memo.encode('utf-8').hex()
        if len(memo_hex) % 2 != 0:
            memo_hex = '0' + memo_hex
        if len(memo_hex) > 2048:
            memo_hex = memo_hex[:2048]
        return memo_hex
    
    def cmd_fund_testnet(self):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            faucet_xlm(self)
            return
        
        print_blue("💰 Fonding testnet...")
        print_yellow("   ⚠️ Il faucet XRP richiede un wallet apposito.")
        print_yellow("   Usa: python3 wallet_cli.py faucet")
        return False
    
    def cmd_export(self, include_private: bool = False):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return None
        
        print_blue("📤 Esportazione wallet...")
        data = self.wallet._xrp_manager.export_wallet("dict", include_private)
        
        if include_private:
            print_yellow("   ⚠️ ATTENZIONE: Chiave privata inclusa!")
        
        print(json.dumps(data, indent=2, default=str))
        return data
    
    def cmd_list_wallets(self):
        wallets = self._get_wallet_list()
        if not wallets:
            print_red("❌ Nessun wallet salvato.")
            return
        
        active = self._get_active_wallet_name()
        
        print("\n📂 WALLET SALVATI")
        print("=" * 80)
        print(f"{'Nome':<18} {'Crypto':<6} {'Rete':<8} {'Indirizzo':<40}")
        print("-" * 60)
        
        for w in wallets:
            marker = "▶" if w["name"] == active else " "
            crypto = w.get("crypto", "XRP")
            network = w.get("network", "testnet")
            print(f"{marker} {w['name']:<17} {crypto:<6} {network:<8} {w['address']}")
        
        print("-" * 60)
        print(f"Totale: {len(wallets)} wallet")
        if active:
            print(f"▶ Attivo: {active}")
        print("=" * 80)
    
    def cmd_switch(self, name: str):
        """Cambia il wallet attivo con quello specificato"""
        # VALIDA IL NOME PRIMA DI USARLO
        if not self._validate_wallet_name(name):
            return
        
        if self._switch_wallet(name):
            print_green(f"✅ Wallet cambiato a: {name}")
            
            wallet_file = self.wallets_dir / f"{name}.json"
            
            # Path traversal protection
            try:
                wallet_file.resolve().relative_to(self.wallets_dir.resolve())
            except ValueError:
                print_red(f"❌ Percorso non valido: {wallet_file}")
                return
            
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        data = json.load(f)
                        network = data.get("network", "testnet")
                        if self.wallet:
                            self.wallet._xrp_manager.set_network(network)
                            print_yellow(f"🌐 Rete impostata a: {network.upper()}")
                except:
                    pass
            
            self.cmd_info()
        else:
            print_red(f"❌ Wallet '{name}' non trovato.")
    
    def cmd_wallet(self, args: List[str]):
        if not args:
            name = self._get_active_wallet_name()
            if name:
                print(f"📂 Wallet attivo: {name}")
                self.cmd_info()
            else:
                print_red("❌ Nessun wallet attivo.")
                print("   Usa 'wallet NOME' per crearne uno nuovo.")
            return
        
        name = args[0]
        if not self._validate_wallet_name(name):
            return
        
        target = self.wallets_dir / f"{name}.json"
        
        # Path traversal protection
        try:
            target.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Percorso non valido: {target}")
            return
        
        if target.exists():
            self.cmd_switch(name)
            return
        
        print(f"\n📂 CREA NUOVO WALLET: {name}")
        print("=" * 60)
        
        crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
        network = input("Rete (testnet/mainnet): ").strip().lower() or "testnet"
        
        self.init(network)
        self.cmd_create(name, crypto, network)

    # ============================================================
    # TRUSTLINE - COMANDI
    # ============================================================

    def cmd_trustlines(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        force_refresh = "--refresh" in args or "-r" in args
        
        print_blue(f"🔗 Recupero trustline ({manager.crypto_type}) su {manager.network.upper()}...")
        trustlines = manager.get_trustlines(force_refresh)
        
        if not trustlines:
            print_yellow("❌ Nessuna trustline trovata.")
            print_yellow("   Crea una trustline con: trustline-set ASSET ISSUER [LIMIT]")
            return
        
        print_bold(f"\n🔗 TRUSTLINE ({manager.crypto_type})")
        print("=" * 100)
        
        if manager.crypto_type == "XRP":
            print(f"{'#':<3} {'Asset':<12} {'Issuer':<40} {'Balance':<15} {'Limit':<15} {'Status'}")
            print("-" * 100)
            for i, tl in enumerate(trustlines, 1):
                status = "✅ Attiva" if tl.get("is_active") else "⏳ In attesa"
                balance = tl.get("balance", 0)
                limit = tl.get("limit", 0)
                print(f"{i:<3} {tl['currency']:<12} {tl['issuer']:<40} {balance:<15.6f} {limit:<15.6f} {status}")
        else:
            print(f"{'#':<3} {'Asset':<12} {'Issuer':<40} {'Balance':<15} {'Limit':<15} {'Status'}")
            print("-" * 100)
            for i, tl in enumerate(trustlines, 1):
                status = "✅ Attiva" if tl.get("is_active") else "⏳ In attesa"
                balance = tl.get("balance", 0)
                limit = tl.get("limit", 0)
                print(f"{i:<3} {tl['asset_code']:<12} {tl['asset_issuer']:<40} {balance:<15.6f} {limit:<15.6f} {status}")
        
        print("=" * 100)
        print(f"Totale: {len(trustlines)} trustline")

    def cmd_trustline_set(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        if len(args) < 2:
            print_red("❌ Specifica asset e issuer.")
            print("Esempio: trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth")
            print("         trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 10000")
            print("         trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 0  # per rimuovere")
            return
        
        asset_code = args[0]
        issuer = args[1]
        limit = float(args[2]) if len(args) > 2 else 0  # Default: 0 = rimuovi
        
        if limit == 0:
            limit_display = "0 (RIMUOVI)"
        else:
            limit_display = str(limit)
        
        print(f"\n🔗 Creazione trustline per {asset_code} su {manager.network.upper()}")
        print("=" * 60)
        print(f"   Asset: {asset_code}")
        print(f"   Issuer: {issuer}")
        print(f"   Limite: {limit_display}")
        print("=" * 60)
        
        confirm = input("   Confermi? (s/n): ")
        if confirm.lower() != 's':
            print("❌ Annullato.")
            return
        
        result = manager.set_trustline(asset_code, issuer, limit)
        
        if result.get("success"):
            print_green(f"\n✅ Trustline {'rimossa' if limit == 0 else 'creata'} per {asset_code}!")
            print(f"   Hash: {result.get('hash', 'unknown')}")
            print(f"   Network: {result.get('network', 'N/A')}")
            print(f"   Limit: {result.get('limit', 'N/A')}")
        else:
            print_red(f"❌ Errore: {result.get('error', 'unknown')}")

    def cmd_trustline_remove(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        if len(args) < 2:
            print_red("❌ Specifica asset e issuer.")
            print("Esempio: trustline-remove RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth")
            return
        
        asset_code = args[0]
        issuer = args[1]
        
        print(f"\n🗑️ Rimozione trustline per {asset_code}")
        print("=" * 60)
        print(f"   Asset: {asset_code}")
        print(f"   Issuer: {issuer}")
        print("=" * 60)
        
        confirm = input("   Confermi? (s/n): ")
        if confirm.lower() != 's':
            print("❌ Annullato.")
            return
        
        result = manager.remove_trustline(asset_code, issuer)
        
        if result.get("success"):
            print_green(f"\n✅ Trustline rimossa per {asset_code}!")
            print(f"   Hash: {result.get('hash', 'unknown')}")
        else:
            print_red(f"❌ Errore: {result.get('error', 'unknown')}")

    def cmd_trustline_info(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        if len(args) < 1:
            print_red("❌ Specifica asset.")
            print("Esempio: trustline-info RLUSD")
            return
        
        asset_code = args[0]
        issuer = args[1] if len(args) > 1 else None
        
        result = manager.get_trustline_balance(asset_code, issuer)
        
        if "error" in result:
            print_red(f"❌ {result['error']}")
            return
        
        print_bold(f"\n📊 INFO TRUSTLINE {asset_code}")
        print("=" * 60)
        print(f"   Asset: {result.get('asset')}")
        print(f"   Issuer: {result.get('issuer')}")
        print(f"   Balance: {result.get('balance', 0):.6f}")
        print(f"   Limit: {result.get('limit', 0):.6f}")
        print(f"   Status: {'✅ Attiva' if result.get('is_active') else '⏳ In attesa'}")
        print("=" * 60)

    # ============================================================
    # TOKEN - COMANDI (INVIO E RICEZIONE)
    # ============================================================

    def cmd_send_token(self, args: List[str]):
        """Invia un token (non XRP) da emettitore a ricevente"""
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        to_address = None
        token = None
        amount = None
        issuer = None
        
        for i, arg in enumerate(args):
            if arg == "--to" and i + 1 < len(args):
                to_address = args[i + 1]
            elif arg == "--token" and i + 1 < len(args):
                token = args[i + 1]
            elif arg == "--amount" and i + 1 < len(args):
                amount = float(args[i + 1])
            elif arg == "--issuer" and i + 1 < len(args):
                issuer = args[i + 1]
        
        if not to_address or not token or not amount:
            print_red("❌ Specifica --to, --token e --amount")
            print("Esempio: send-token --to r... --token Arg0 --amount 1000")
            return
        
        if not issuer:
            issuer = manager.get_address()
            print_yellow(f"📌 Usando issuer: {issuer} (wallet corrente)")
        
        print(f"\n📤 Invio token {token} da {manager.get_address()} a {to_address}")
        print(f"   Issuer: {issuer}")
        print(f"   Amount: {amount}")
        print("=" * 60)
        
        confirm = input("   Confermi? (s/n): ")
        if confirm.lower() != 's':
            print("❌ Annullato.")
            return
        
        try:
            from xrpl.models.transactions import Payment
            from xrpl.transaction import autofill, sign, submit_and_wait
            from xrpl.clients import JsonRpcClient
            from xrpl.models.amounts import IssuedCurrencyAmount
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/",
                "devnet": "https://s.devnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(manager.network, urls["testnet"]))
            
            wallet = manager.get_wallet("default", 0)
            
            if len(token) == 3:
                currency = token
            else:
                currency_hex = token.encode('utf-8').hex().upper()
                currency = currency_hex.ljust(40, '0')
            
            amount_obj = IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer,
                value=str(amount)
            )
            
            payment = Payment(
                account=wallet.classic_address,
                destination=to_address,
                amount=amount_obj
            )
            
            print(f"📡 Invio transazione...")
            tx = autofill(payment, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)
            
            tx_hash = response.result.get("hash", "unknown")
            
            print_green(f"\n✅ {amount} {token} inviati con successo!")
            print(f"   Hash: {tx_hash}")
            print(f"   Da: {wallet.classic_address}")
            print(f"   A: {to_address}")
            print(f"   Issuer: {issuer}")
            
        except Exception as e:
            print_red(f"❌ Errore: {e}")

    def cmd_receive_token(self, args: List[str]):
        """Mostra come ricevere un token (crea trustline)"""
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return
        
        token = None
        issuer = None
        limit = None
        
        for i, arg in enumerate(args):
            if arg == "--token" and i + 1 < len(args):
                token = args[i + 1]
            elif arg == "--issuer" and i + 1 < len(args):
                issuer = args[i + 1]
            elif arg == "--limit" and i + 1 < len(args):
                limit = float(args[i + 1])
        
        if not token or not issuer:
            print_red("❌ Specifica --token e --issuer")
            print("Esempio: receive-token --token Arg0 --issuer r... --limit 1000000")
            return
        
        if not limit:
            limit = 1000000.0
        
        print_bold(f"\n📥 RICEZIONE TOKEN {token}")
        print("=" * 60)
        print(f"   Token: {token}")
        print(f"   Issuer: {issuer}")
        print(f"   Limite: {limit}")
        print("=" * 60)
        print("\n📋 Per ricevere questo token, devi creare una trustline:")
        print(f"   python3 wallet_cli.py trustline-set {token} {issuer} {limit}")
        print("\n💡 Dopo aver creato la trustline, l'emettitore potrà inviarti i token.")
        print("   Verifica con: python3 wallet_cli.py trustlines --refresh")


    # ============================================================
    # RETICULUM - COMANDI (USANO LA STESSA ISTANZA)
    # ============================================================

    def cmd_reticulum(self, args: List[str]):
        """Gestione Reticulum"""
        if not RETICULUM_AVAILABLE:
            print_red("❌ Reticulum non disponibile")
            return
        
        if not args:
            self._reticulum_help()
            return

        subcmd = args[0].lower() if args else ""
        
        if subcmd == "init":
            self._reticulum_init()
        elif subcmd == "gateway" and len(args) > 1:
            if args[1] == "start":
                self._reticulum_gateway_start()
            elif args[1] == "stop":
                self._reticulum_gateway_stop()
            elif args[1] == "status":
                self._reticulum_gateway_status()
            else:
                print(f"❌ Sottocomando sconosciuto: {args[1]}")
        elif subcmd == "wallet" and len(args) > 1:
            if args[1] == "start":
                self._reticulum_wallet_start()
            elif args[1] == "stop":
                self._reticulum_wallet_stop()
            elif args[1] == "status":
                self._reticulum_wallet_status()
            else:
                print(f"❌ Sottocomando sconosciuto: {args[1]}")
        elif subcmd == "discover":
            self._reticulum_discover()
        elif subcmd == "discover-wallets":
            self._reticulum_discover_wallets()
        elif subcmd == "peers":
            self._reticulum_peers()
        elif subcmd == "best":
            asset = args[1] if len(args) > 1 else None
            self._reticulum_best_gateway(asset)
        elif subcmd == "send":
            self._reticulum_send(args[1:])
        else:
            print(f"❌ Comando sconosciuto: {subcmd}")

    def _reticulum_wallet_start(self):
        """Avvia il wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        status = self.reticulum.get_status()
        if status.get('is_wallet', False):
            print_yellow(f"⚠️ Wallet già avviato")
            return
        
        print_blue("📡 Avvio wallet Reticulum...")
        self.reticulum.start_wallet(blocking=False)
        
        time.sleep(1)
        status = self.reticulum.get_status()
        if status.get('is_wallet', False):
            print_green(f"✅ Wallet avviato")
            print_yellow(f"   Wallet Name: {status.get('wallet_name', 'Wallet')}")
            print_yellow(f"   Wallet Hash: {status.get('wallet_address', 'N/A')}")
        else:
            print_red("❌ Errore nell'avvio del wallet")

    def _reticulum_wallet_stop(self):
        """Ferma il wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        self.reticulum.stop_wallet()
        print_green("✅ Wallet fermato")

    def _reticulum_wallet_status(self):
        """Mostra lo stato del wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        status = self.reticulum.get_status()
        print_bold("\n📊 STATO WALLET")
        print("=" * 60)
        print(f"   Running:          {status.get('running', False)}")
        print(f"   Wallet:           {status.get('is_wallet', False)}")
        print(f"   PID:              {status.get('pid', 'N/A')}")
        started = status.get('started_at')
        if started:
            started_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started))
        else:
            started_str = 'N/A'
        print(f"   Started:          {started_str}")
        print(f"   Wallet Address:   {status.get('wallet_address', 'N/A')}")
        print(f"   Wallet Name:      {status.get('wallet_name', 'N/A')}")
        print(f"   Wallet Count:     {status.get('wallet_count', 0)}")
        print("=" * 60)

    def _reticulum_help(self):
        print("Comandi Reticulum:")
        print("  reticulum init          - Inizializza Reticulum (già fatto all'avvio)")
        print("  reticulum gateway start - Avvia gateway")
        print("  reticulum gateway stop  - Ferma gateway")
        print("  reticulum gateway status - Stato gateway")
        print("  reticulum discover      - Cerca gateway")
        print("  reticulum discover-wallets - Cerca wallet")
        print("  reticulum peers         - Mostra peer con metriche")
        print("  reticulum best ASSET    - Miglior gateway per asset")
        print("  reticulum send ...      - Invia transazione via Reticulum")

    def _reticulum_init(self):
        """Inizializza Reticulum (già fatto all'avvio, ma utile per reset)"""
        if not self.reticulum_initialized:
            self._init_reticulum()
        else:
            print_yellow("⚠️ Reticulum già inizializzato")
        
        if self.reticulum:
            status = self.reticulum.get_status()
            print_green("📡 Stato Reticulum:")
            print(f"   Gateway Address: {status.get('gateway_address', 'N/A')}")
            print(f"   Wallet Address: {status.get('wallet_address', 'N/A')}")
            print(f"   Cache size: {status.get('cache_size', 0)}")
            if status.get('is_gateway', False):
                print(f"   Gateway Running: ✅ Sì (PID: {status.get('pid')})")
            else:
                print(f"   Gateway Running: ❌ No")

    def _reticulum_gateway_start(self):
        """Avvia il gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        status = self.reticulum.get_status()
        if status.get('is_gateway', False):
            print_yellow(f"⚠️ Gateway già avviato (PID: {status.get('pid')})")
            return
        
        print_blue("📡 Avvio gateway Reticulum...")
        self.reticulum.start_gateway(blocking=False)
        
        time.sleep(1)
        status = self.reticulum.get_status()
        if status.get('is_gateway', False):
            print_green(f"✅ Gateway avviato (PID: {status.get('pid')})")
            print_yellow(f"   Gateway Name: {status.get('gateway_name', 'Gateway')}")
            print_yellow(f"   Gateway Hash: {status.get('gateway_address', 'N/A')}")
        else:
            print_red("❌ Errore nell'avvio del gateway")

    def _reticulum_gateway_stop(self):
        """Ferma il gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        self.reticulum.stop_gateway()
        print_green("✅ Gateway fermato")

    def _reticulum_gateway_status(self):
        """Mostra lo stato del gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        status = self.reticulum.get_status()
        print_bold("\n📊 STATO GATEWAY")
        print("=" * 60)
        print(f"   Running:          {status.get('running', False)}")
        print(f"   Gateway:          {status.get('is_gateway', False)}")
        print(f"   Wallet:           {status.get('is_wallet', False)}")
        print(f"   PID:              {status.get('pid', 'N/A')}")
        started = status.get('started_at')
        if started:
            started_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started))
        else:
            started_str = 'N/A'
        print(f"   Started:          {started_str}")
        print(f"   Gateway Address:  {status.get('gateway_address', 'N/A')}")
        print(f"   Wallet Address:   {status.get('wallet_address', 'N/A')}")
        print(f"   Gateway Name:     {status.get('gateway_name', 'N/A')}")
        print(f"   Wallet Name:      {status.get('wallet_name', 'N/A')}")
        print(f"   Gateway Count:    {status.get('gateway_count', 0)}")
        print(f"   Wallet Count:     {status.get('wallet_count', 0)}")
        
        # ============================================================
        # STATO INTERNET - CONFIGURAZIONE E REALE
        # ============================================================
        use_internet = status.get('use_internet', False)
        has_internet = status.get('has_internet', False)
        print(f"\n   🌐 INTERNET:")
        print(f"      Config:        {'ON' if use_internet else 'OFF'}")
        print(f"      Connessione:   {'✅' if has_internet else '❌'}")
        
        # Latenze ledger
        xrp_reachable = status.get('xrp_reachable', False)
        xrp_latency = status.get('xrp_latency_ms')
        stellar_reachable = status.get('stellar_reachable', False)
        stellar_latency = status.get('stellar_latency_ms')
        
        print(f"\n   📊 LEDGER:")
        print(f"      XRP:          {'✅' if xrp_reachable else '❌'} {xrp_latency}ms" if xrp_latency else f"      XRP:          {'✅' if xrp_reachable else '❌'}")
        print(f"      Stellar:      {'✅' if stellar_reachable else '❌'} {stellar_latency}ms" if stellar_latency else f"      Stellar:      {'✅' if stellar_reachable else '❌'}")
        
        print("=" * 60)

    def _reticulum_discover(self):
        """Cerca gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        print_blue("🔍 Ricerca gateway Reticulum...")
        gateways = self.reticulum.discover_gateways()
        
        print_bold(f"\n🔍 GATEWAY TROVATI ({len(gateways)})")
        print("=" * 60)
        if gateways:
            for gw in gateways:
                print(f"   Nome: {gw.get('name', 'Sconosciuto')}")
                print(f"   Hash: {gw.get('gateway_id', '?')}")
                last_seen = gw.get('last_seen')
                if last_seen:
                    seen_str = time.strftime('%H:%M:%S', time.localtime(last_seen))
                    print(f"   Ultimo visto: {seen_str}")
                print("-" * 40)
        else:
            print("   ❌ Nessun gateway trovato")
        print("=" * 60)

    def _reticulum_discover_wallets(self):
        """Cerca wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        print_blue("🔍 Ricerca wallet Reticulum...")
        wallets = self.reticulum.discover_wallets()
        
        print_bold(f"\n🔍 WALLET TROVATI ({len(wallets)})")
        print("=" * 60)
        if wallets:
            for w in wallets:
                print(f"   Nome: {w.get('name', 'Sconosciuto')}")
                print(f"   Hash: {w.get('wallet_id', '?')}")
                last_seen = w.get('last_seen')
                if last_seen:
                    seen_str = time.strftime('%H:%M:%S', time.localtime(last_seen))
                    print(f"   Ultimo visto: {seen_str}")
                print("-" * 40)
        else:
            print("   ❌ Nessun wallet trovato")
        print("=" * 60)

    def _reticulum_peers(self):
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        peers = self.metrics.get_all_peers()
        
        if not peers:
            print_yellow("⚠️ Nessun peer conosciuto")
            return
        
        # Verifica se ci sono dati radio
        has_radio = any(p.get('rssi') is not None or p.get('snr') is not None for p in peers)
        
        if has_radio:
            print_bold(f"\n🔍 PEER CONOSCIUTI ({len(peers)})")
            print("=" * 210)
            print(f"{'Nome':<16} {'ID':<34} {'Hops':<6} {'RTT':<10} {'RSSI':<10} {'SNR':<10} {'XRP':<14} {'Stellar':<14} {'Rep':<5} {'Internet':<9} {'Ultimo visto':<15} {'Assets'}")
            print("-" * 210)
            
            for p in peers:
                name = str(p.get('name', 'UNKNOWN'))[:14]
                gid = str(p.get('gateway_id', 'N/A'))[:32]
                
                hops = p.get('hops')
                hops_str = str(hops) if hops is not None else '?'
                
                latency = p.get('latency_ms')
                latency_str = f"{latency}ms" if latency is not None else '?ms'
                
                # RSSI
                rssi = p.get('rssi')
                if rssi is not None:
                    if rssi > -60:
                        rssi_color = Colors.GREEN
                    elif rssi > -80:
                        rssi_color = Colors.YELLOW
                    else:
                        rssi_color = Colors.RED
                    rssi_str = f"{rssi_color}{rssi:.1f}dBm{Colors.RESET}"
                else:
                    rssi_str = 'N/A'
                
                # SNR
                snr = p.get('snr')
                if snr is not None:
                    if snr > 15:
                        snr_color = Colors.GREEN
                    elif snr > 8:
                        snr_color = Colors.YELLOW
                    else:
                        snr_color = Colors.RED
                    snr_str = f"{snr_color}{snr:.1f}dB{Colors.RESET}"
                else:
                    snr_str = 'N/A'
                
                # XRP
                xrp_reachable = p.get('xrp_reachable', False)
                xrp_latency = p.get('xrp_latency_ms')
                if xrp_reachable and xrp_latency:
                    xrp_str = f"✅{xrp_latency}ms"
                elif xrp_reachable:
                    xrp_str = "✅ OK"
                else:
                    xrp_str = "❌"
                
                # Stellar
                stellar_reachable = p.get('stellar_reachable', False)
                stellar_latency = p.get('stellar_latency_ms')
                if stellar_reachable and stellar_latency:
                    stellar_str = f"✅{stellar_latency}ms"
                elif stellar_reachable:
                    stellar_str = "✅ OK"
                else:
                    stellar_str = "❌"
                
                rep = str(p.get('reputation', 50))
                internet_icon = "🌐" if p.get('has_internet', False) else "📡"
                
                # ============================================================
                # ULTIMO VISTO - FORMATTATO
                # ============================================================
                last_seen = p.get('last_seen')
                last_seen_str = self._format_time_ago(last_seen)
                
                assets = p.get('assets', [])
                if isinstance(assets, list):
                    assets_str = ', '.join(assets[:2])
                    if len(assets) > 2:
                        assets_str += f" +{len(assets)-2}"
                else:
                    assets_str = str(assets)[:15]
                
                print(f"{name:<16} {gid:<34} {hops_str:<6} {latency_str:<10} {rssi_str:<10} {snr_str:<10} {xrp_str:<14} {stellar_str:<14} {rep:<5} {internet_icon:<9} {last_seen_str:<15} {assets_str}")
        else:
            # Visualizzazione standard senza radio
            print_bold(f"\n🔍 PEER CONOSCIUTI ({len(peers)})")
            print("=" * 180)
            print(f"{'Nome':<18} {'ID':<36} {'Hops':<6} {'RTT':<10} {'XRP':<14} {'Stellar':<14} {'Rep':<5} {'Rel':<6} {'Internet':<9} {'Ultimo visto':<15} {'Assets'}")
            print("-" * 180)
            
            for p in peers:
                name = str(p.get('name', 'UNKNOWN'))[:16]
                gid = str(p.get('gateway_id', 'N/A'))[:34]
                
                hops = p.get('hops')
                hops_str = str(hops) if hops is not None else '?'
                
                latency = p.get('latency_ms')
                latency_str = f"{latency}ms" if latency is not None else '?ms'
                
                xrp_reachable = p.get('xrp_reachable', False)
                xrp_latency = p.get('xrp_latency_ms')
                if xrp_reachable and xrp_latency:
                    xrp_str = f"✅{xrp_latency}ms"
                elif xrp_reachable:
                    xrp_str = "✅ OK"
                else:
                    xrp_str = "❌"
                
                stellar_reachable = p.get('stellar_reachable', False)
                stellar_latency = p.get('stellar_latency_ms')
                if stellar_reachable and stellar_latency:
                    stellar_str = f"✅{stellar_latency}ms"
                elif stellar_reachable:
                    stellar_str = "✅ OK"
                else:
                    stellar_str = "❌"
                
                rep = str(p.get('reputation', 50))
                rel = f"{p.get('reliability', 0):.2f}" if p.get('reliability') else '0.00'
                internet_icon = "🌐" if p.get('has_internet', False) else "📡"
                
                # ============================================================
                # ULTIMO VISTO - FORMATTATO
                # ============================================================
                last_seen = p.get('last_seen')
                last_seen_str = self._format_time_ago(last_seen)
                
                assets = p.get('assets', [])
                if isinstance(assets, list):
                    assets_str = ', '.join(assets[:3])
                    if len(assets) > 3:
                        assets_str += f" +{len(assets)-3}"
                else:
                    assets_str = str(assets)[:20]
                
                print(f"{name:<18} {gid:<36} {hops_str:<6} {latency_str:<10} {xrp_str:<14} {stellar_str:<14} {rep:<5} {rel:<6} {internet_icon:<9} {last_seen_str:<15} {assets_str}")
        
        print("=" * 180)
        
        # Statistiche
        stats = self.metrics.get_stats() if hasattr(self.metrics, 'get_stats') else {}
        if stats:
            print(f"\n📊 Statistiche:")
            print(f"   Totale peer: {stats.get('total_peers', 0)}")
            print(f"   Online: {stats.get('online_peers', 0)}")
            print(f"   Reputazione media: {stats.get('avg_reputation', 0)}")
            if stats.get('avg_latency_ms'):
                print(f"   Latenza media Reticulum: {stats.get('avg_latency_ms')}ms")
            if stats.get('avg_rssi'):
                print(f"   RSSI medio: {stats.get('avg_rssi')}dBm")

    def _reticulum_best_gateway(self, asset: str):
        """Mostra il miglior gateway per un asset"""
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        if not asset:
            print_red("❌ Specifica un asset (es. RLUSD)")
            return
        
        best = self.metrics.get_best_gateway(asset)
        
        if best:
            print_green(f"\n✅ Miglior gateway per {asset}:")
            print(f"   Nome: {best.get('name', 'UNKNOWN')}")
            print(f"   ID: {best.get('gateway_id', 'N/A')}")
            print(f"   Hops: {best.get('hops', '?')}")
            print(f"   RTT Reticulum: {best.get('latency_ms', '?')}ms")
            
            # Latenze ledger
            xrp_latency = best.get('xrp_latency_ms')
            xrp_reachable = best.get('xrp_reachable', False)
            stellar_latency = best.get('stellar_latency_ms')
            stellar_reachable = best.get('stellar_reachable', False)
            
            print(f"   XRP: {'✅' if xrp_reachable else '❌'} {xrp_latency}ms" if xrp_latency else f"   XRP: {'✅' if xrp_reachable else '❌'}")
            print(f"   Stellar: {'✅' if stellar_reachable else '❌'} {stellar_latency}ms" if stellar_latency else f"   Stellar: {'✅' if stellar_reachable else '❌'}")
            
            # Metriche radio
            rssi = best.get('rssi')
            snr = best.get('snr')
            if rssi is not None:
                print(f"   RSSI: {rssi:.1f}dBm")
            if snr is not None:
                print(f"   SNR: {snr:.1f}dB")
            
            print(f"   Reputation: {best.get('reputation', 50)}")
            print(f"   Reliability: {best.get('reliability', 0):.2f}")
            print(f"   Internet: {'✅' if best.get('has_internet', False) else '❌'}")
            print(f"   Networks: {', '.join(best.get('networks', [])) or 'N/A'}")
            print(f"   Assets: {', '.join(best.get('assets', [])) or 'N/A'}")
            print(f"   Fee: {best.get('fee', 'N/A')} {best.get('fee_asset', '')}")
        else:
            print_red(f"❌ Nessun gateway trovato per {asset}")

    def _reticulum_send(self, args: List[str]):
        """Invia transazione via Reticulum"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        if not self.wallet or not self.wallet._xrp_manager.is_loaded():
            print_red("❌ Nessun wallet caricato!")
            return

        to_addr = None
        amount = None
        asset = "XRP"
        gateway_id = None

        for i, arg in enumerate(args):
            if arg == "--to" and i + 1 < len(args):
                to_addr = args[i + 1]
            elif arg == "--amount" and i + 1 < len(args):
                try:
                    amount = float(args[i + 1])
                except:
                    pass
            elif arg == "--asset" and i + 1 < len(args):
                asset = args[i + 1]
            elif arg == "--gateway" and i + 1 < len(args):
                gateway_id = args[i + 1]

        if not to_addr or not amount:
            print_red("❌ Specifica --to e --amount")
            print("Esempio: reticulum send --to r... --amount 10 --asset XRP")
            return

        if not gateway_id:
            print_blue("🔍 Cerco gateway disponibili...")
            gateways = self.reticulum.discover_gateways()
            if not gateways:
                print_red("❌ Nessun gateway disponibile")
                return
            gateway_id = gateways[0].get('gateway_id')
            print_yellow(f"📌 Usando gateway: {gateway_id[:16]}...")

        manager = self.wallet._xrp_manager
        tx_data = {
            "from": manager.get_address(),
            "to": to_addr,
            "amount": str(amount),
            "asset": asset,
            "network": manager.network,
            "timestamp": int(time.time())
        }

        print_blue(f"📡 Invio transazione via Reticulum...")
        try:
            response = self.reticulum.send_transaction_via_reticulum(gateway_id, tx_data)
            if response.get("success"):
                print_green(f"✅ Transazione inviata!")
                print(f"   Hash: {response.get('hash', 'N/A')}")
            else:
                print_red(f"❌ Errore: {response.get('error', 'Sconosciuto')}")
        except Exception as e:
            print_red(f"❌ Errore durante l'invio: {e}")


    def _reticulum_request_info(self):
        """Richiedi info a un gateway specifico"""
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        print_blue("🔍 Gateway disponibili:")
        gateways = self.reticulum.discover_gateways()
        if not gateways:
            print_red("❌ Nessun gateway trovato")
            return
        
        # Filtra il proprio gateway
        my_id = self.reticulum.gateway_address
        filtered = [g for g in gateways if g.get('gateway_id') != my_id]
        
        if not filtered:
            print_yellow("⚠️ Solo il proprio gateway trovato, nessun peer disponibile")
            return
        
        for i, gw in enumerate(filtered, 1):
            name = gw.get('name', 'UNKNOWN')
            gw_id = gw.get('gateway_id', '?')
            hops = gw.get('hops', '?')
            rssi = gw.get('rssi')
            rssi_str = f" RSSI:{rssi:.1f}dBm" if rssi is not None else ""
            print(f"   {i}) {name} ({gw_id[:16]}...) Hops:{hops}{rssi_str}")
        
        try:
            choice = int(input("\nScegli gateway (numero): ").strip())
            if 1 <= choice <= len(filtered):
                gateway_id = filtered[choice - 1].get('gateway_id')
                if gateway_id:
                    print_blue(f"📡 Richiedo info a {gateway_id[:16]}...")
                    success = self.metrics.request_gateway_info(gateway_id)
                    if success:
                        print_green("✅ Richiesta inviata e risposta ricevuta!")
                        # ============================================================
                        # MOSTRA SOLO IL PEER APPENA INTERROGATO!
                        # ============================================================
                        self._show_single_peer(gateway_id)
                    else:
                        print_red("❌ Errore nella richiesta (vedi log sopra)")
            else:
                print_red("❌ Scelta non valida")
        except ValueError:
            print_red("❌ Inserisci un numero valido")


    def _show_single_peer(self, gateway_id: str):
        """Mostra un singolo peer in formato tabella"""
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        peers = self.metrics.get_all_peers()
        peer = None
        for p in peers:
            if p.get('gateway_id') == gateway_id:
                peer = p
                break
        
        if not peer:
            print_yellow("⚠️ Peer non trovato nel database")
            return
        
        # Mostra in formato tabella (stile _reticulum_peers ma per un solo peer)
        print_bold(f"\n🔍 PEER: {peer.get('name', 'UNKNOWN')}")
        print("=" * 120)
        print(f"{'ID':<38} {'Hops':<6} {'RTT':<10} {'XRP':<14} {'Stellar':<14} {'Rep':<5} {'Internet':<9} {'Ultimo visto':<15}")
        print("-" * 120)
        
        gid = str(peer.get('gateway_id', 'N/A'))
        hops = peer.get('hops', '?')
        hops_str = str(hops) if hops is not None else '?'
        
        latency = peer.get('latency_ms')
        latency_str = f"{latency}ms" if latency is not None else '?ms'
        
        xrp_reachable = peer.get('xrp_reachable', False)
        xrp_latency = peer.get('xrp_latency_ms')
        if xrp_reachable and xrp_latency:
            xrp_str = f"✅{xrp_latency}ms"
        elif xrp_reachable:
            xrp_str = "✅ OK"
        else:
            xrp_str = "❌"
        
        stellar_reachable = peer.get('stellar_reachable', False)
        stellar_latency = peer.get('stellar_latency_ms')
        if stellar_reachable and stellar_latency:
            stellar_str = f"✅{stellar_latency}ms"
        elif stellar_reachable:
            stellar_str = "✅ OK"
        else:
            stellar_str = "❌"
        
        rep = str(peer.get('reputation', 50))
        internet_icon = "🌐" if peer.get('has_internet', False) else "📡"
        
        last_seen = peer.get('last_seen')
        last_seen_str = self._format_time_ago(last_seen)
        
        print(f"{gid:<38} {hops_str:<6} {latency_str:<10} {xrp_str:<14} {stellar_str:<14} {rep:<5} {internet_icon:<9} {last_seen_str:<15}")
        print("=" * 120)
        
        # Mostra anche gli Assets
        assets = peer.get('assets', [])
        if isinstance(assets, list) and assets:
            print(f"   Assets: {', '.join(assets)}")
        
        # Mostra Fee
        fee = peer.get('fee', 'N/A')
        fee_asset = peer.get('fee_asset', '')
        if fee != 'N/A':
            print(f"   Fee: {fee} {fee_asset}")


# ============================================================
# 6. MODALITÀ INTERATTIVA - VERSIONE DEFINITIVA
# ============================================================

def interactive_mode():
    """Modalità interattiva con Reticulum sempre attivo"""
    cli = WalletCLI()
    cli.init()
    cli._interactive_mode = True
    
    # Reticulum è già inizializzato all'avvio
    gateway_active = False
    
    print_bold("\n" + "=" * 60)
    print_bold("    💰 WALLET CLI - MODALITÀ INTERATTIVA")
    print_bold("=" * 60)
    print("")
    print_green("📡 Reticulum attivo per tutta la sessione")
    
    try:
        while True:
            print("\n" + "-" * 40)
            print("  1) Crea wallet")
            print("  2) Importa wallet")
            print("  3) Mostra saldo")
            print("  4) Mostra indirizzo")
            print("  5) Deriva indirizzi")
            print("  6) Invia pagamento")
            print("  7) Info wallet")
            print("  8) Storico")
            print("  9) Fund testnet (XLM)")
            print(" 10) Esporta")
            print(" 11) Lista wallet")
            print(" 12) Cambia wallet")
            print(" 13) Trustline")
            print(" 14) Invia token")
            print(" 15) Reticulum")
            print("  0) Esci")
            
            # Mostra stato Reticulum
            if cli.reticulum:
                status = cli.reticulum.get_status()
                if status.get('is_gateway', False):
                    print_yellow(f"  📡 Gateway attivo (PID: {status.get('pid')})")
                elif status.get('is_wallet', False):
                    print_yellow(f"  📡 Wallet attivo (PID: {status.get('pid')})")
                elif status.get('running', False):
                    print_cyan("  📡 Reticulum attivo")
                else:
                    print_red("  ❌ Reticulum non attivo")
            print("-" * 40)
            
            choice = input("\nScelta: ").strip()
            
            if choice == '0':
                print_green("👋 Arrivederci!")
                break
            
            elif choice == '1':
                name = input("Nome (default): ").strip() or "default"
                crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
                network = input("Rete (testnet/mainnet): ").strip().lower() or "testnet"
                cli.cmd_create(name, crypto, network)
            
            elif choice == '2':
                seed = input("Inserisci seed/mnemonic/numeri: ").strip()
                if seed:
                    name = input("Nome (imported): ").strip() or "imported"
                    crypto = input("Crypto (auto/XRP/XLM): ").strip().upper() or "auto"
                    network = input("Rete (testnet/mainnet): ").strip().lower() or "testnet"
                    cli.cmd_import(seed, name, crypto, network)
            
            elif choice == '3':
                cli.cmd_balance(True)
            
            elif choice == '4':
                cli.cmd_address()
            
            elif choice == '5':
                keyword = input("Keyword (default): ").strip() or "default"
                count = int(input("Numero (5): ").strip() or "5")
                cli.cmd_derive(keyword, count)
            
            elif choice == '6':
                to_addr = input("Indirizzo destinatario: ").strip()
                amount = float(input("Ammontare: ").strip())
                memo = input("Memo: ").strip()
                if to_addr and amount > 0:
                    cli.cmd_send(to_addr, amount, memo)
                else:
                    print_red("❌ Dati non validi")
            
            elif choice == '7':
                cli.cmd_info()
            
            elif choice == '8':
                limit = int(input("Numero transazioni (10): ").strip() or "10")
                cli.cmd_history(limit)
            
            elif choice == '9':
                cli.cmd_fund_testnet()
            
            elif choice == '10':
                private = input("Includi chiave privata? (s/N): ").strip().lower() == 's'
                cli.cmd_export(private)
            
            elif choice == '11':
                cli.cmd_list_wallets()
            
            elif choice == '12':
                name = input("Nome wallet: ").strip()
                if name:
                    cli.cmd_switch(name)
            
            elif choice == '13':
                print("\n🔗 GESTIONE TRUSTLINE")
                print("  1) Mostra trustline")
                print("  2) Crea trustline")
                print("  3) Rimuovi trustline")
                print("  4) Info trustline")
                sub_choice = input("Scelta: ").strip()
                if sub_choice == '1':
                    cli.cmd_trustlines(["--refresh"])
                elif sub_choice == '2':
                    asset = input("Asset (es. RLUSD): ").strip()
                    issuer = input("Issuer address: ").strip()
                    limit = input("Limite (0 per rimuovere): ").strip()
                    args = [asset, issuer]
                    if limit:
                        args.append(limit)
                    else:
                        args.append("0")
                    cli.cmd_trustline_set(args)
                elif sub_choice == '3':
                    asset = input("Asset: ").strip()
                    issuer = input("Issuer address: ").strip()
                    cli.cmd_trustline_remove([asset, issuer])
                elif sub_choice == '4':
                    asset = input("Asset: ").strip()
                    issuer = input("Issuer (opzionale): ").strip()
                    cli.cmd_trustline_info([asset] + ([issuer] if issuer else []))
            
            elif choice == '14':
                to_addr = input("Indirizzo destinatario: ").strip()
                token = input("Nome token (es. Arg0): ").strip()
                amount = float(input("Ammontare: ").strip())
                issuer = input("Issuer (opzionale, invio per wallet corrente): ").strip()
                
                if to_addr and token and amount:
                    args = ["--to", to_addr, "--token", token, "--amount", str(amount)]
                    if issuer:
                        args += ["--issuer", issuer]
                    cli.cmd_send_token(args)
                else:
                    print_red("❌ Dati non validi")
            
            elif choice == '15':
                print("\n🌐 GESTIONE RETICULUM")
                print("  1) Stato")
                print("  2) Avvia gateway")
                print("  3) Ferma gateway")
                print("  4) Scopri gateway")
                print("  5) Scopri wallet")
                print("  6) Peer metriche")
                print("  7) Miglior gateway")
                print("  8) Richiedi info gateway")
                print("  9) Invia transazione")
                sub_choice = input("Scelta: ").strip()
                
                if sub_choice == '1':
                    cli._reticulum_gateway_status()
                elif sub_choice == '2':
                    cli._reticulum_gateway_start()
                elif sub_choice == '3':
                    cli._reticulum_gateway_stop()
                elif sub_choice == '4':
                    cli._reticulum_discover()
                elif sub_choice == '5':
                    cli._reticulum_discover_wallets()
                elif sub_choice == '6':
                    cli._reticulum_peers()
                elif sub_choice == '7':
                    asset = input("Asset (es. RLUSD): ").strip()
                    if asset:
                        cli._reticulum_best_gateway(asset)
                    else:
                        print_red("❌ Specifica un asset")
                elif sub_choice == '8':
                    cli._reticulum_request_info()
                elif sub_choice == '9':
                    to_addr = input("Indirizzo destinatario: ").strip()
                    amount = float(input("Ammontare: ").strip())
                    asset = input("Asset (XRP): ").strip() or "XRP"
                    if to_addr and amount:
                        cli._reticulum_send(["--to", to_addr, "--amount", str(amount), "--asset", asset])
                    else:
                        print_red("❌ Dati non validi")
                else:
                    print_red("❌ Scelta non valida")
    
    except KeyboardInterrupt:
        print("\n")
        print_yellow("⚠️ Interrotto dall'utente")
    
    finally:
        # Ferma metriche
        if hasattr(cli, 'metrics') and cli.metrics:
            try:
                cli.metrics.stop_query_loop()
            except:
                pass
        
        # Ferma gateway se attivo
        if cli.reticulum:
            status = cli.reticulum.get_status()
            if status.get('is_gateway', False):
                print("\n🛑 Fermando il gateway...")
                cli.reticulum.stop_gateway()
            print_green("👋 Arrivederci!")


# ============================================================
# 5. MAIN
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Wallet CLI - Gestione wallet XRP/XLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ESEMPI:
  # Modalità interattiva (RACCOMANDATA per Reticulum)
  python wallet_cli.py interactive
  
  # Creazione
  python wallet_cli.py create --name mio_wallet --crypto XRP --network testnet
  
  # Importa mnemonica
  python wallet_cli.py import --seed "abandon abandon ..." --name mio_wallet
  
  # Saldo
  python wallet_cli.py balance
  
  # Info
  python wallet_cli.py info
  
  # Storico
  python wallet_cli.py history --limit 10
  
  # Invia XRP
  python wallet_cli.py send --to r... --amount 1.5 --memo "test"
  
  # Invia Token
  python wallet_cli.py send-token --to r... --token Arg0 --amount 1000
  
  # Ricevi Token
  python wallet_cli.py receive-token --token Arg0 --issuer r... --limit 1000000
  
  # Lista wallet
  python wallet_cli.py list-wallets
  
  # Cambia wallet
  python wallet_cli.py switch mio_wallet
  
  # Trustline
  python wallet_cli.py trustlines --refresh
  python wallet_cli.py trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 10000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandi disponibili')
    
    create_parser = subparsers.add_parser('create', help='Crea un nuovo wallet')
    create_parser.add_argument('--name', default='default', help='Nome wallet')
    create_parser.add_argument('--crypto', default='XRP', choices=['XRP', 'XLM'], help='Crypto')
    create_parser.add_argument('--network', default='testnet', choices=['testnet', 'mainnet', 'devnet'], help='Rete')
    
    import_parser = subparsers.add_parser('import', help='Importa un wallet')
    import_parser.add_argument('--seed', required=True, help='Seed, mnemonic o numeri Xaman')
    import_parser.add_argument('--name', default='imported', help='Nome wallet')
    import_parser.add_argument('--crypto', default='auto', choices=['auto', 'XRP', 'XLM'], help='Crypto')
    import_parser.add_argument('--network', default='testnet', choices=['testnet', 'mainnet', 'devnet'], help='Rete')
    
    balance_parser = subparsers.add_parser('balance', help='Mostra saldo')
    balance_parser.add_argument('--refresh', action='store_true', help='Forza refresh')
    
    subparsers.add_parser('address', help='Mostra indirizzo')
    
    derive_parser = subparsers.add_parser('derive', help='Deriva indirizzi')
    derive_parser.add_argument('--keyword', default='default', help='Keyword derivazione')
    derive_parser.add_argument('--count', type=int, default=5, help='Numero indirizzi')
    
    send_parser = subparsers.add_parser('send', help='Invia pagamento')
    send_parser.add_argument('--to', required=True, help='Indirizzo destinatario')
    send_parser.add_argument('--amount', required=True, type=float, help='Ammontare')
    send_parser.add_argument('--memo', default='', help='Memo')
    
    subparsers.add_parser('info', help='Mostra info wallet')
    
    history_parser = subparsers.add_parser('history', help='Mostra storico')
    history_parser.add_argument('--limit', type=int, default=10, help='Numero transazioni')
    
    subparsers.add_parser('fund', help='Fonda wallet su testnet (solo XLM)')
    
    export_parser = subparsers.add_parser('export', help='Esporta wallet')
    export_parser.add_argument('--private', action='store_true', help='Includi chiave privata')
    
    subparsers.add_parser('list-wallets', help='Lista tutti i wallet salvati')
    
    switch_parser = subparsers.add_parser('switch', help='Cambia wallet attivo')
    switch_parser.add_argument('name', help='Nome wallet')
    
    wallet_parser = subparsers.add_parser('wallet', help='Crea o cambia wallet')
    wallet_parser.add_argument('name', nargs='?', default=None, help='Nome wallet')
    
    subparsers.add_parser('interactive', help='Modalità interattiva')
    
    # ============================================================
    # TRUSTLINE - COMANDI
    # ============================================================

    trustlines_parser = subparsers.add_parser('trustlines', help='Mostra trustline')
    trustlines_parser.add_argument('--refresh', '-r', action='store_true', help='Forza refresh')

    trustline_set_parser = subparsers.add_parser('trustline-set', help='Crea trustline')
    trustline_set_parser.add_argument('asset', help='Asset code (es. RLUSD)')
    trustline_set_parser.add_argument('issuer', help='Issuer address')
    trustline_set_parser.add_argument('limit', nargs='?', type=float, default=0, help='Limite (default: 0 = rimuovi)')

    trustline_remove_parser = subparsers.add_parser('trustline-remove', help='Rimuovi trustline')
    trustline_remove_parser.add_argument('asset', help='Asset code')
    trustline_remove_parser.add_argument('issuer', help='Issuer address')

    trustline_info_parser = subparsers.add_parser('trustline-info', help='Info trustline')
    trustline_info_parser.add_argument('asset', help='Asset code')
    trustline_info_parser.add_argument('issuer', nargs='?', help='Issuer address (opzionale)')

    # ============================================================
    # TOKEN - COMANDI
    # ============================================================

    send_token_parser = subparsers.add_parser('send-token', help='Invia un token (non XRP)')
    send_token_parser.add_argument('--to', required=True, help='Indirizzo destinatario')
    send_token_parser.add_argument('--token', required=True, help='Nome del token (es. Arg0)')
    send_token_parser.add_argument('--amount', required=True, type=float, help='Quantità da inviare')
    send_token_parser.add_argument('--issuer', help='Issuer del token (default: wallet corrente)')

    receive_token_parser = subparsers.add_parser('receive-token', help='Prepara la ricezione di un token')
    receive_token_parser.add_argument('--token', required=True, help='Nome del token')
    receive_token_parser.add_argument('--issuer', required=True, help='Indirizzo dell\'emettitore')
    receive_token_parser.add_argument('--limit', type=float, default=1000000.0, help='Limite massimo')

    # ============================================================
    # RETICULUM - COMANDI (RIMOSSI PERCHÉ USARE INTERACTIVE)
    # ============================================================
    # I comandi Reticulum da CLI non sono più supportati
    # Usa la modalità interattiva: python wallet_cli.py interactive
    
    args, unknown = parser.parse_known_args()
    
    cli = WalletCLI()
    
    if args.command == 'interactive':
        interactive_mode()
    
    elif args.command == 'create':
        cli.cmd_create(args.name, args.crypto, args.network)
    
    elif args.command == 'import':
        cli.cmd_import(args.seed, args.name, args.crypto, args.network)
    
    elif args.command == 'balance':
        cli.init()
        cli.cmd_balance(args.refresh)
    
    elif args.command == 'address':
        cli.init()
        cli.cmd_address()
    
    elif args.command == 'derive':
        cli.init()
        cli.cmd_derive(args.keyword, args.count)
    
    elif args.command == 'send':
        cli.init()
        cli.cmd_send(args.to, args.amount, args.memo)
    
    elif args.command == 'info':
        cli.init()
        cli.cmd_info()
    
    elif args.command == 'history':
        cli.init()
        cli.cmd_history(args.limit)
    
    elif args.command == 'fund':
        cli.init()
        cli.cmd_fund_testnet()
    
    elif args.command == 'export':
        cli.init()
        cli.cmd_export(args.private)
    
    elif args.command == 'list-wallets':
        cli.init()
        cli.cmd_list_wallets()
    
    elif args.command == 'switch':
        cli.init()
        cli.cmd_switch(args.name)
    
    elif args.command == 'wallet':
        cli.init()
        if args.name:
            cli.cmd_wallet([args.name])
        else:
            cli.cmd_wallet([])
    
    elif args.command == 'trustlines':
        cli.init()
        cli.cmd_trustlines(sys.argv[2:])

    elif args.command == 'trustline-set':
        cli.init()
        args_list = [args.asset, args.issuer]
        if args.limit is not None:
            args_list.append(str(args.limit))
        cli.cmd_trustline_set(args_list)

    elif args.command == 'trustline-remove':
        cli.init()
        cli.cmd_trustline_remove([args.asset, args.issuer])

    elif args.command == 'trustline-info':
        cli.init()
        cli.cmd_trustline_info([args.asset] + ([args.issuer] if args.issuer else []))

    elif args.command == 'send-token':
        cli.init()
        cli.cmd_send_token(sys.argv[2:])

    elif args.command == 'receive-token':
        cli.init()
        cli.cmd_receive_token(sys.argv[2:])
    
    else:
        parser.print_help()


# ============================================================
# 7. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import sys
    # Se nessun argomento o solo "interactive"
    if len(sys.argv) == 1:
        sys.argv.append("interactive")
    main()