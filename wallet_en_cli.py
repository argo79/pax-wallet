#!/usr/bin/env python3
"""
paxwallet.py - PAX Wallet CLI for XRP/XLM with multi-wallet, trustline, token and Reticulum support
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
# VERSION
# ============================================================
VERSION = "0.9.1b"
__version__ = VERSION


# ============================================================
# PATCH FOR RETICULUM - MUST BE FIRST!
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
# XLM COMMANDS IMPORT
# ============================================================

try:
    from commands.xlm_commands import send_xlm, history_xlm, info_xlm, faucet_xlm
    XLM_AVAILABLE = True
except ImportError as e:
    XLM_AVAILABLE = False
    def send_xlm(cli):
        print("❌ XLM command not available. Install stellar-sdk")
    def history_xlm(cli):
        print("❌ XLM command not available. Install stellar-sdk")
    def info_xlm(cli):
        print("❌ XLM command not available. Install stellar-sdk")
    def faucet_xlm(cli):
        print("❌ XLM command not available. Install stellar-sdk")


# ============================================================
# RETICULUM MANAGER IMPORT
# ============================================================

try:
    from reticulum.reticulum_manager import ReticulumManager, ReticulumConfig
    RETICULUM_AVAILABLE = True
except ImportError as e:
    RETICULUM_AVAILABLE = False
    print(f"⚠️ Reticulum not available: {e}")


# ============================================================
# METRICS IMPORT
# ============================================================

try:
    from reticulum.gateway_metrics import GatewayMetrics
    METRICS_AVAILABLE = True
except ImportError as e:
    METRICS_AVAILABLE = False
    print(f"⚠️ Metrics not available: {e}")


# ============================================================
# 2. OUTPUT COLORS
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
        self.contacts_file = Path("contacts.json")
        self._interactive_mode = False
        
        # ============================================================
        # RETICULUM - SINGLETON FOR THE ENTIRE SESSION
        # ============================================================
        self.reticulum: Optional[ReticulumManager] = None
        self.reticulum_initialized = False
        self.reticulum_config = ReticulumConfig()
        self.metrics = None

        # Initialize Reticulum at CLI startup (once)
        if RETICULUM_AVAILABLE:
            self._init_reticulum()

    def _validate_wallet_name(self, name: str) -> bool:
        """Check that the wallet name is safe (only valid characters)"""
        if not name:
            print_red("❌ Wallet name is empty")
            return False
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            print_red(f"❌ Invalid wallet name: {name}")
            print_yellow("   Use only letters, numbers, underscore (_) and dash (-)")
            return False
        return True

    def _init_reticulum(self):
        """Initialize Reticulum ONCE at CLI startup"""
        if not RETICULUM_AVAILABLE:
            return
        
        if not self.reticulum_initialized:
            # 1. CREATE RETICULUM MANAGER
            self.reticulum = ReticulumManager()
            
            # 2. CREATE METRICS AND SET IN MANAGER (BEFORE init!)
            if METRICS_AVAILABLE:
                try:
                    self.metrics = GatewayMetrics(self.reticulum.identity)
                    self.metrics.set_my_gateway_id(self.reticulum.gateway_address)
                    
                    # ============================================================
                    # 🔥 SET use_internet FROM CONFIG!
                    # ============================================================
                    if hasattr(self.reticulum, 'config'):
                        self.metrics.set_use_internet(self.reticulum.config.use_internet)
                        self.metrics.set_ledger_timeout(self.reticulum.config.ledger_timeout_seconds)
                        self.metrics.set_ledger_check_interval(self.reticulum.config.ledger_check_interval)
                    
                    # 🔥 SET METRICS IN MANAGER (BEFORE init!)
                    self.reticulum.set_metrics(self.metrics)
                    print_green("📡 Metrics created and linked")
                except Exception as e:
                    print_yellow(f"⚠️ Error starting metrics: {e}")
                    self.metrics = None
            
            # 3. NOW init() WILL FIND metrics NOT None
            self.reticulum.init()
            self.reticulum_initialized = True
            
            # Start query loop
            if METRICS_AVAILABLE and self.metrics:
                try:
                    self.metrics.start_query_loop(
                        interval=3600,
                        max_peers=10,
                        max_hops=3
                    )
                    print_green("📡 Gateway metrics started")
                except Exception as e:
                    print_yellow(f"⚠️ Error starting query loop: {e}")
            else:
                print_yellow("⚠️ Metrics not available, some Reticulum functions may not work")
            
            status = self.reticulum.get_status()
            print_green("📡 Reticulum active for the entire session")
            print_yellow(f"   Gateway Hash: {status.get('gateway_address', 'N/A')}")
            print_yellow(f"   Wallet Hash:  {status.get('wallet_address', 'N/A')}")
            if self.metrics:
                print_green(f"   Metrics: ✅ Available")
            else:
                print_red(f"   Metrics: ❌ NOT AVAILABLE")

    def init(self, network: str = None):
        """Inizializza il wallet"""
        active = self._get_active_wallet_name()
        
        # ============================================================
        # VALIDA IL NOME DEL WALLET ATTIVO PRIMA DI USARLO
        # ============================================================
        if active:
            # Validazione del nome
            if not self._validate_wallet_name(active):
                print_red(f"⚠️ Nome wallet attivo non valido: {active}")
                active = None
        
        if active:
            wallet_file = self.wallets_dir / f"{active}.json"
            
            # Path traversal protection
            try:
                wallet_file.resolve().relative_to(self.wallets_dir.resolve())
            except ValueError:
                print_red(f"❌ Percorso non valido: {wallet_file}")
                network = "testnet"
                crypto = "XRP"
                active = None
            
            if active and wallet_file.exists():
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
    
    def _get_contacts(self) -> List[Dict]:
        if not self.contacts_file.exists():
            return []
        try:
            with open(self.contacts_file) as f:
                data = json.load(f)
                return data.get("contacts", [])
        except:
            return []
    
    def _search_contact(self, name: str) -> Optional[Dict]:
        contacts = self._get_contacts()
        for c in contacts:
            if c.get("name", "").lower() == name.lower():
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
            print_red(f"❌ Invalid path: {dest}")
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
        
        print_green(f"✅ Wallet '{name}' saved with address: {correct_address}")
        print_yellow(f"🌐 Network saved: {manager.network.upper()}")
        print_yellow(f"🪙 Crypto saved: {manager.crypto_type}")
        return True
    
    def _switch_wallet(self, name: str) -> bool:
        """Switch to the specified wallet"""
        # VALIDATE NAME BEFORE USING IT
        if not self._validate_wallet_name(name):
            return False
        
        source = self.wallets_dir / f"{name}.json"
        
        # Path traversal protection
        try:
            source.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Invalid path: {source}")
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
            
            print_green(f"✅ Switched to wallet: {name}")
            print_yellow(f"🌐 Network: {saved_network.upper()}")
            print_yellow(f"🪙 Crypto: {saved_crypto}")
            return True
            
        except Exception as e:
            print_red(f"❌ Error switching wallet: {e}")
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
                            print_yellow(f"🌐 Network set to: {saved_network.upper()}")
                        
                        if saved_crypto != manager.crypto_type:
                            manager.set_crypto(saved_crypto)
                            print_yellow(f"🪙 Crypto set to: {saved_crypto}")
                except:
                    pass
    
    def cmd_remove_wallet(self):
        """Rimuovi un wallet dalla lista"""
        wallets = self._get_wallet_list()
        if not wallets:
            print_red("❌ Nessun wallet salvato.")
            return
        
        active = self._get_active_wallet_name()
        
        print("\n🗑️  RIMUOVI WALLET")
        print("=" * 60)
        print(f"{'#':<4} {'Nome':<18} {'Crypto':<6} {'Rete':<8}")
        print("-" * 60)
        
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w["name"] == active else " "
            print(f"{i:<4} {marker} {w['name']:<17} {w.get('crypto', 'XRP'):<6} {w.get('network', 'testnet'):<8}")
        
        print("-" * 60)
        print("=" * 60)
        
        choice = input("\nNumero wallet da rimuovere (o Invio per saltare): ").strip()
        if not choice:
            return
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(wallets):
                wallet_name = wallets[idx]["name"]
                if wallet_name == active:
                    print_red(f"❌ Non puoi rimuovere il wallet attivo: {wallet_name}")
                    return
                confirm = input(f"   Rimuovere wallet '{wallet_name}'? (s/N): ").strip().lower()
                if confirm == 's':
                    wallet_file = self.wallets_dir / f"{wallet_name}.json"
                    if wallet_file.exists():
                        wallet_file.unlink()
                        print_green(f"✅ Wallet '{wallet_name}' rimosso!")
                    else:
                        print_yellow(f"⚠️ File non trovato: {wallet_file}")
                else:
                    print_yellow("❌ Rimozione annullata")
            else:
                print_red("❌ Numero non valido")
        else:
            print_yellow("❌ Inserisci un numero valido")

    # ============================================================
    # PARSE TX DATE
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
    # FORMAT TIME AGO
    # ============================================================
    
    def _format_time_ago(self, timestamp: int) -> str:
        """Format timestamp as 'X minutes ago', 'X hours ago', etc."""
        if not timestamp:
            return "Never"
        
        now = int(time.time())
        diff = now - timestamp
        
        if diff < 60:
            return "Just now"
        elif diff < 3600:
            mins = diff // 60
            return f"{mins} min ago" if mins > 1 else "1 min ago"
        elif diff < 86400:
            hours = diff // 3600
            return f"{hours} hours ago" if hours > 1 else "1 hour ago"
        elif diff < 604800:
            days = diff // 86400
            return f"{days} days ago" if days > 1 else "1 day ago"
        else:
            weeks = diff // 604800
            return f"{weeks} weeks ago" if weeks > 1 else "1 week ago"
    
    # ============================================================
    # PRINT TRANSACTIONS
    # ============================================================
    
    def _print_transactions(self, transactions: List, address: str) -> None:
        from datetime import datetime
        import base64
        
        manager = self.wallet._xrp_manager if self.wallet else None
        
        print("\n┌────┬─────────────────────┬────────────┬──────────────────┬────────────┬──────────────────────────────────────────────────┬────────────────────┐")
        print(f"│ #  │ Date/Time           │ Type       │ Amount           │ Fee        │ From/To                                           │ Memo               │")
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
                    direction = "RECEIVED"
                    from_to = f"From: {sender}"
                elif sender == address:
                    direction = "SENT"
                    from_to = f"To: {destination}"
                else:
                    direction = "OTHER"
                    from_to = f"{sender} → {destination}"
                
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
                
                if len(from_to) > 48:
                    from_to_display = from_to[:45] + "..."
                else:
                    from_to_display = from_to
                
                if len(memo_display) > 18:
                    memo_display = memo_display[:15] + "..."
                
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {direction:<10} │ {amount_str:<16} │ {fee_str:<10} │ {from_to_display:<48} │ {memo_display:<18} │")
            else:
                print(f"│ {idx:<2} │ {date_str[:19]:<19} │ {tx_type:<10} │ {'':<16} │ {fee_str:<10} │ {'':<48} │ {'':<18} │")
        
        print("└────┴─────────────────────┴────────────┴──────────────────┴────────────┴──────────────────────────────────────────────────┴────────────────────┘")
        print(f"Total: {len(transactions)} transactions shown")

    def cmd_test_gateways(self):
        """Testa tutti i gateway disponibili e mostra le performance"""
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        print_blue("🔍 Test di tutti i gateway in corso...")
        
        gateways = self.reticulum.discover_gateways()
        
        if not gateways:
            print_red("❌ Nessun gateway trovato")
            return
        
        print_bold(f"\n🧪 TEST GATEWAY ({len(gateways)})")
        print("=" * 120)
        print(f"{'#':<3} {'Nome':<16} {'Status':<10} {'RTT':<10} {'XRP':<12} {'Stellar':<12} {'Hops':<6} {'Score'}")
        print("-" * 120)
        
        results = []
        for idx, gw in enumerate(gateways, 1):
            name = gw.get('name', 'UNKNOWN')[:14]
            gw_id = gw.get('gateway_id', '')
            hops = gw.get('hops', '?')
            
            # 🔥 USA request_gateway_info() INVECE DI send_ping()
            start = time.time()
            try:
                success = self.metrics.request_gateway_info(gw_id)
                rtt = (time.time() - start) * 1000
                if success:
                    status = "✅ Online"
                    # Prendi i dati aggiornati
                    peers = self.metrics.get_all_peers()
                    for p in peers:
                        if p.get('gateway_id') == gw_id:
                            gw = p
                            break
                else:
                    status = "❌ Offline"
                    rtt = None
            except Exception as e:
                status = "❌ Offline"
                rtt = None
            
            # Calcola score
            score = 0
            if rtt and status == "✅ Online":
                score += max(0, 50 - rtt/10)
            
            xrp = "✅" if gw.get('xrp_reachable') else "❌"
            stellar = "✅" if gw.get('stellar_reachable') else "❌"
            
            if gw.get('xrp_reachable'):
                score += 10
            if gw.get('stellar_reachable'):
                score += 10
            if gw.get('has_internet'):
                score += 5
            
            rtt_str = f"{rtt:.1f}ms" if rtt else "Timeout"
            
            print(f"{idx:<3} {name:<16} {status:<10} {rtt_str:<10} {xrp:<12} {stellar:<12} {hops:<6} {score:.0f}")
            results.append({"name": name, "status": status, "score": score, "gw_id": gw_id})
        
        print("=" * 120)
        
        # Miglior gateway
        online = [r for r in results if r["status"] == "✅ Online"]
        if online:
            best = max(online, key=lambda x: x["score"])
            print(f"\n🏆 Miglior gateway: {best['name']} (Score: {best['score']:.0f})")
            print(f"   ID: {best['gw_id']}")
        else:
            print("\n❌ Nessun gateway online")

    # ============================================================
    # 4. MAIN COMMANDS
    # ============================================================
    
    def cmd_create(self, name: str = "default", crypto: str = "XRP", network: str = "testnet"):
        if not self.wallet:
            self.init(network)
        
        if not self._validate_wallet_name(name):
            return None
        
        # ============================================================
        # 🔥 VALIDA CRYPTO
        # ============================================================
        crypto = crypto.upper()
        if crypto not in ["XRP", "XLM"]:
            print_red(f"❌ Crypto non supportata: {crypto}")
            print_yellow("   Usa XRP o XLM")
            return None
        
        # ============================================================
        # 🔥 VALIDA RETE
        # ============================================================
        network = network.lower()
        if network not in ["testnet", "mainnet", "devnet"]:
            print_red(f"❌ Rete non supportata: {network}")
            print_yellow("   Usa: testnet, mainnet o devnet")
            return None
        
        print_blue(f"📤 Creating {crypto} wallet on {network.upper()}...")
        
        manager = self.wallet._xrp_manager
        if network != manager.network:
            manager.set_network(network)
            print_yellow(f"🌐 Network set to: {network.upper()}")
        
        # ============================================================
        # 🔥 CHIEDE 12 O 24 PAROLE
        # ============================================================
        print("\n   🔐 Choose seed word count:")
        print("      1) 12 words (128 bit - standard, easier to write)")
        print("      2) 24 words (256 bit - maximum security)")
        print("")
        choice = input("   Choice (1 or 2, default 2): ").strip()
        
        if choice == "1":
            strength = 128
            word_count = 12
            print_cyan("   🔐 Using 12 words")
        else:
            strength = 256
            word_count = 24
            print_cyan("   🔐 Using 24 words (maximum security)")
        
        # ============================================================
        # 🔥 CHIEDE PASSPHRASE (OSCURATA)
        # ============================================================
        print("")
        print("   🔐 Passphrase (optional, press Enter to skip):")
        print("      If you forget it, the wallet is unrecoverable.")
        print("")
        
        import getpass
        passphrase = getpass.getpass("   Enter passphrase: ").strip()
        
        if passphrase:
            confirm = getpass.getpass("   Confirm passphrase: ").strip()
            if confirm != passphrase:
                print_red("❌ Passphrases do not match!")
                return None
            print_cyan(f"   🔐 Passphrase set")
        else:
            print_yellow("   ⚠️ No passphrase")
        
        # ============================================================
        # 🔥 CREA WALLET
        # ============================================================
        result = self.wallet.create_wallet(name, crypto, strength=strength, passphrase=passphrase)
        
        print_green(f"\n✅ Wallet created on {network.upper()}!")
        print(f"   Identity: {result['identity_id']}")
        print(f"   Address: {result['address']}")
        print(f"   Mnemonic: {result['mnemonic']}")
        print(f"   Word Count: {result['word_count']}")
        if passphrase:
            print(f"   Passphrase: {'*' * len(passphrase)}")
        print(f"   Seed: {result.get('seed', 'N/A')}")
        
        if passphrase:
            print("")
            print_yellow("   ⚠️ WARNING: The passphrase is NOT stored in the wallet!")
            print_yellow("   Store it in a safe place, SEPARATE from the seed.")
            print_yellow("   Without the passphrase you CANNOT recover the wallet.")
        
        self.wallet.save()
        self._save_wallet_as(name)
        self._set_active_wallet_name(name)
        
        return result
    
    def cmd_import(self, seed_input: str, name: str = "imported", crypto: str = "auto", network: str = "testnet"):
        if not self.wallet:
            self.init(network)
        
        if not self._validate_wallet_name(name):
            return None
        
        # ============================================================
        # 🔥 VALIDA RETE
        # ============================================================
        network = network.lower()
        if network not in ["testnet", "mainnet", "devnet"]:
            print_red(f"❌ Rete non supportata: {network}")
            print_yellow("   Usa: testnet, mainnet o devnet")
            return None
        
        try:
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
                crypto_param = crypto.upper()
                # 🔥 VALIDA CRYPTO
                if crypto_param not in ["XRP", "XLM"]:
                    print_red(f"❌ Crypto non supportata: {crypto_param}")
                    print_yellow("   Usa XRP, XLM o auto")
                    return None
            
            # ============================================================
            # 🔥 SE MNEMONICA, CHIEDI PASSPHRASE (OSCURATA)
            # ============================================================
            passphrase = ""
            if import_type == "bip39":
                print("")
                print("   🔐 Passphrase (optional, press Enter to skip):")
                print("      Enter the passphrase if the wallet was created with one.")
                print("")
                import getpass
                passphrase = getpass.getpass("   Enter passphrase: ").strip()
                if passphrase:
                    print_cyan(f"   🔐 Passphrase used")
                else:
                    print_yellow("   ⚠️ No passphrase")
            
            # ============================================================
            # 🔥 GESTISCI NUMERI XAMAN
            # ============================================================
            if len(numbers_parts) == 8 and all(p.isdigit() and len(p) == 6 for p in numbers_parts):
                import_type = "numbers"
                print_cyan(f"   🔢 Numeri Xaman rilevati: {numbers_parts}")
                print_cyan("   🔄 Conversione numeri Xaman via Node.js...")
                result = self.wallet.import_wallet(" ".join(numbers_parts), name, crypto_param)
            else:
                result = self.wallet.import_wallet(seed_input, name, crypto_param, passphrase=passphrase)
            
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
            
            if passphrase:
                print(f"   Passphrase: {'*' * len(passphrase)}")
            
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
            
        except Exception as e:
            print_red(f"❌ Errore importazione: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _cmd_balance_xlm(self, refresh: bool = False):
        manager = self.wallet._xrp_manager
        try:
            balance = manager.get_balance(refresh)
            print_green(f"   Balance: {balance:.7f} XLM")
            return balance
        except Exception as e:
            print_red(f"   ❌ Error: {e}")
            return None
    
    def cmd_balance(self, refresh: bool = False):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return self._cmd_balance_xlm(refresh)
        
        print_blue(f"💰 Fetching XRP balance on {manager.network.upper()}...")
        
        try:
            balance = manager.get_balance(refresh)
            print_green(f"   Balance: {balance:.6f} XRP")
            return balance
        except Exception as e:
            print_red(f"   ❌ Error: {e}")
            return None
    
    def cmd_address(self):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return None
        
        address = self.wallet.get_address()
        print_green(f"   Address: {address}")
        return address
    
    def cmd_derive(self, keyword: str = "default", count: int = 5):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return
        
        crypto_type = self.wallet._xrp_manager.crypto_type
        
        # 🔥 FOR STELLAR: SHOW ONLY THE ADDRESS
        if crypto_type == "XLM":
            try:
                address = self.wallet.get_address()
                print_green(f"📤 Stellar Address: {address}")
            except Exception as e:
                print_red(f"❌ Error: {e}")
            return
        
        # FOR XRP: multiple derivation
        print_blue(f"📤 Deriving {count} XRP addresses (keyword: {keyword})...")
        
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
            print_red("❌ No wallet loaded!")
            return
        
        info = manager.get_seed_info()
        
        print_bold("\n📊 COMPLETE WALLET INFO")
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
    # HISTORY
    # ============================================================
    
    def cmd_history(self, limit: int = 10):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            history_xlm(self, ["--limit", str(limit)])
            return
        
        address = manager.get_address()
        network = manager.network
        
        print(f"\n📜 XRP TRANSACTION HISTORY ({network.upper()})")
        print("=" * 80)
        print(f"Address: {address}")
        print(f"Limit:   {limit} transactions")
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
            
            print("🔄 Requesting ledger...")
            response = client.request(request)
            
            if response.status != ResponseStatus.SUCCESS:
                print(f"❌ Error: {response.status}")
                return
            
            result = response.result
            transactions = result.get("transactions", [])
            
            if not transactions:
                print("❌ No transactions found.")
                return
            
            self._print_transactions(transactions, address)
            
            if network == "mainnet":
                explorer = f"https://xrpscan.com/account/{address}"
            elif network == "testnet":
                explorer = f"https://testnet.xrpl.org/accounts/{address}"
            else:
                explorer = f"https://devnet.xrpl.org/accounts/{address}"
            print(f"\n🔗 View all: {explorer}")
            
        except Exception as e:
            print_red(f"   ❌ Error: {e}")
            if network == "mainnet":
                explorer = f"https://xrpscan.com/account/{address}"
            elif network == "testnet":
                explorer = f"https://testnet.xrpl.org/accounts/{address}"
            else:
                explorer = f"https://devnet.xrpl.org/accounts/{address}"
            print(f"\n🔗 View on: {explorer}")
    
    # ============================================================
    # 4. MAIN COMMANDS - SEND
    # ============================================================

    def cmd_send(self, to_address: str, amount: float, memo: str = ""):
        """Send XRP or XLM payment with confirmation"""
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return None
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # XLM handling
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return self._send_xlm(to_address, amount, memo)
        
        # XRP handling
        return self._send_xrp(to_address, amount, memo)

    def _send_xlm(self, to_address: str, amount: float, memo: str = ""):
        """Send XLM with summary and confirmation"""
        # Show summary
        if not self._confirm_transaction("XLM", to_address, amount, memo):
            return None
        
        print_blue("📡 Sending...")
        
        args = [to_address, str(amount)]
        if memo:
            args.append(memo)
        
        send_xlm(self, args)
        return True

    def _send_xrp(self, to_address: str, amount: float, memo: str = ""):
        """Send XRP with summary and confirmation"""
        # Show summary
        if not self._confirm_transaction("XRP", to_address, amount, memo):
            return None
        
        print_blue("📡 Sending...")
        
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
            
            # Check balance
            balance_drops = get_balance(source_address, client)
            balance_xrp = balance_drops / 1_000_000
            
            if balance_xrp < amount:
                print_red(f"   ❌ Insufficient balance! You have: {balance_xrp:.6f} XRP")
                return None
            
            amount_drops = str(int(amount * 1_000_000))
            
            payment_params = {
                "account": source_address,
                "amount": amount_drops,
                "destination": to_address,
            }
            
            # Add memo if present
            if memo:
                memo_hex = self._encode_memo_hex(memo)
                payment_params["memos"] = [Memo(memo_data=memo_hex)]
            
            payment = Payment(**payment_params)
            tx = autofill(payment, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)
            
            tx_hash = response.result.get("hash", "unknown")
            
            print_green(f"   ✅ Payment sent!")
            print(f"   Hash: {tx_hash}")
            
            new_balance = get_balance(source_address, client) / 1_000_000
            print(f"   New balance: {new_balance:.6f} XRP")
            
            return tx_hash
            
        except Exception as e:
            print_red(f"   ❌ Error: {e}")
            return None

    def _confirm_transaction(self, crypto: str, to_address: str, amount: float, memo: str = "") -> bool:
        """Show summary and ask for confirmation"""
        manager = self.wallet._xrp_manager
        
        print_bold(f"\n📤 SEND {crypto}")
        print("=" * 60)
        print(f"   Wallet:    {self._get_active_wallet_name()}")
        print(f"   From:      {manager.get_address()}")
        print(f"   To:        {to_address}")
        print(f"   Amount:    {amount} {crypto}")
        if memo:
            print(f"   📝 Memo:    {memo}")
        print("=" * 60)
        print("")
        
        confirm = input("   Confirm sending? (y/n): ")
        if confirm.lower() != 'y':
            print_red("❌ Transaction cancelled.")
            return False
        
        return True

    def _encode_memo_hex(self, memo: str) -> str:
        """Encode memo to hex"""
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
            print_red("❌ No wallet loaded!")
            return None
        
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            faucet_xlm(self)
            return
        
        print_blue("💰 Funding testnet...")
        print_yellow("   ⚠️ XRP faucet requires a specific wallet.")
        print_yellow("   Use: python3 wallet_cli.py faucet")
        return False
    
    def cmd_export(self, include_private: bool = False):
        if not self.wallet:
            self.init()
        
        if not self.wallet._xrp_manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return None
        
        print_blue("📤 Exporting wallet...")
        data = self.wallet._xrp_manager.export_wallet("dict", include_private)
        
        if include_private:
            print_yellow("   ⚠️ WARNING: Private key included!")
        
        print(json.dumps(data, indent=2, default=str))
        return data
    
    def cmd_list_wallets(self):
        wallets = self._get_wallet_list()
        if not wallets:
            print_red("❌ Nessun wallet salvato.")
            return
        
        active = self._get_active_wallet_name()
        
        print("\n📂 WALLET SALVATI")
        print("=" * 100)
        print(f"{'#':<4} {'Nome':<18} {'Crypto':<6} {'Rete':<8} {'Indirizzo':<42}")
        print("-" * 100)
        
        for i, w in enumerate(wallets, 1):
            marker = "▶" if w["name"] == active else " "
            crypto = w.get("crypto", "XRP")
            network = w.get("network", "testnet")
            address = w.get("address", "unknown")
            print(f"{i:<4} {marker} {w['name']:<17} {crypto:<6} {network:<8} {address:<42}")
        
        print("-" * 100)
        print(f"Totale: {len(wallets)} wallet")
        if active:
            print(f"▶ Attivo: {active}")
        print("=" * 100)
        
        # 🔥 CHIEDE SE MOSTRARE I DETTAGLI DI UN WALLET
        print("\n📋 Vuoi vedere i dettagli di un wallet?")
        print("   (premi Invio per saltare)")
        choice = input("Numero wallet (o Invio): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(wallets):
                wallet_name = wallets[idx]["name"]
                # 🔥 CAMBIA WALLET E MOSTRA INFO
                if self._switch_wallet(wallet_name):
                    print_green(f"✅ Wallet cambiato a: {wallet_name}")
                    self.cmd_info()  # 🔥 USA cmd_info() CHE ESISTE GIÀ!
                else:
                    print_red(f"❌ Errore nel cambio wallet")
    
    def cmd_switch(self, name: str):
        """Switch to the specified wallet"""
        # VALIDATE NAME BEFORE USING IT
        if not self._validate_wallet_name(name):
            return
        
        if self._switch_wallet(name):
            print_green(f"✅ Switched to wallet: {name}")
            
            wallet_file = self.wallets_dir / f"{name}.json"
            
            # Path traversal protection
            try:
                wallet_file.resolve().relative_to(self.wallets_dir.resolve())
            except ValueError:
                print_red(f"❌ Invalid path: {wallet_file}")
                return
            
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        data = json.load(f)
                        network = data.get("network", "testnet")
                        if self.wallet:
                            self.wallet._xrp_manager.set_network(network)
                            print_yellow(f"🌐 Network set to: {network.upper()}")
                except:
                    pass
            
            self.cmd_info()
        else:
            print_red(f"❌ Wallet '{name}' not found.")
    
    def cmd_wallet(self, args: List[str]):
        if not args:
            name = self._get_active_wallet_name()
            if name:
                print(f"📂 Active wallet: {name}")
                self.cmd_info()
            else:
                print_red("❌ No active wallet.")
                print("   Use 'wallet NAME' to create a new one.")
            return
        
        name = args[0]
        if not self._validate_wallet_name(name):
            return
        
        target = self.wallets_dir / f"{name}.json"
        
        # Path traversal protection
        try:
            target.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Invalid path: {target}")
            return
        
        if target.exists():
            self.cmd_switch(name)
            return
        
        print(f"\n📂 CREATE NEW WALLET: {name}")
        print("=" * 60)
        
        crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
        network = input("Network (testnet/mainnet): ").strip().lower() or "testnet"
        
        self.init(network)
        self.cmd_create(name, crypto, network)

    # ============================================================
    # TRUSTLINE - COMMANDS
    # ============================================================

    def cmd_trustlines(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return
        
        force_refresh = "--refresh" in args or "-r" in args
        
        print_blue(f"🔗 Fetching trustlines ({manager.crypto_type}) on {manager.network.upper()}...")
        trustlines = manager.get_trustlines(force_refresh)
        
        if not trustlines:
            print_yellow("❌ No trustlines found.")
            print_yellow("   Create a trustline with: trustline-set ASSET ISSUER [LIMIT]")
            return
        
        print_bold(f"\n🔗 TRUSTLINES ({manager.crypto_type})")
        print("=" * 100)
        
        if manager.crypto_type == "XRP":
            print(f"{'#':<3} {'Asset':<12} {'Issuer':<40} {'Balance':<15} {'Limit':<15} {'Status'}")
            print("-" * 100)
            for i, tl in enumerate(trustlines, 1):
                status = "✅ Active" if tl.get("is_active") else "⏳ Pending"
                balance = tl.get("balance", 0)
                limit = tl.get("limit", 0)
                print(f"{i:<3} {tl['currency']:<12} {tl['issuer']:<40} {balance:<15.6f} {limit:<15.6f} {status}")
        else:
            print(f"{'#':<3} {'Asset':<12} {'Issuer':<40} {'Balance':<15} {'Limit':<15} {'Status'}")
            print("-" * 100)
            for i, tl in enumerate(trustlines, 1):
                status = "✅ Active" if tl.get("is_active") else "⏳ Pending"
                balance = tl.get("balance", 0)
                limit = tl.get("limit", 0)
                print(f"{i:<3} {tl['asset_code']:<12} {tl['asset_issuer']:<40} {balance:<15.6f} {limit:<15.6f} {status}")
        
        print("=" * 100)
        print(f"Total: {len(trustlines)} trustlines")

    def cmd_trustline_set(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return
        
        if len(args) < 2:
            print_red("❌ Specify asset and issuer.")
            print("Example: trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth")
            print("         trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 10000")
            print("         trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 0  # to remove")
            return
        
        asset_code = args[0]
        issuer = args[1]
        limit = float(args[2]) if len(args) > 2 else 0  # Default: 0 = remove
        
        if limit == 0:
            limit_display = "0 (REMOVE)"
        else:
            limit_display = str(limit)
        
        print(f"\n🔗 Creating trustline for {asset_code} on {manager.network.upper()}")
        print("=" * 60)
        print(f"   Asset: {asset_code}")
        print(f"   Issuer: {issuer}")
        print(f"   Limit: {limit_display}")
        print("=" * 60)
        
        confirm = input("   Confirm? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled.")
            return
        
        result = manager.set_trustline(asset_code, issuer, limit)
        
        if result.get("success"):
            print_green(f"\n✅ Trustline {'removed' if limit == 0 else 'created'} for {asset_code}!")
            print(f"   Hash: {result.get('hash', 'unknown')}")
            print(f"   Network: {result.get('network', 'N/A')}")
            print(f"   Limit: {result.get('limit', 'N/A')}")
        else:
            print_red(f"❌ Error: {result.get('error', 'unknown')}")

    def cmd_trustline_remove(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return
        
        if len(args) < 2:
            print_red("❌ Specify asset and issuer.")
            print("Example: trustline-remove RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth")
            return
        
        asset_code = args[0]
        issuer = args[1]
        
        print(f"\n🗑️ Removing trustline for {asset_code}")
        print("=" * 60)
        print(f"   Asset: {asset_code}")
        print(f"   Issuer: {issuer}")
        print("=" * 60)
        
        confirm = input("   Confirm? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled.")
            return
        
        result = manager.remove_trustline(asset_code, issuer)
        
        if result.get("success"):
            print_green(f"\n✅ Trustline removed for {asset_code}!")
            print(f"   Hash: {result.get('hash', 'unknown')}")
        else:
            print_red(f"❌ Error: {result.get('error', 'unknown')}")

    def cmd_trustline_info(self, args: List[str]):
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
            return
        
        if len(args) < 1:
            print_red("❌ Specify asset.")
            print("Example: trustline-info RLUSD")
            return
        
        asset_code = args[0]
        issuer = args[1] if len(args) > 1 else None
        
        result = manager.get_trustline_balance(asset_code, issuer)
        
        if "error" in result:
            print_red(f"❌ {result['error']}")
            return
        
        print_bold(f"\n📊 TRUSTLINE INFO {asset_code}")
        print("=" * 60)
        print(f"   Asset: {result.get('asset')}")
        print(f"   Issuer: {result.get('issuer')}")
        print(f"   Balance: {result.get('balance', 0):.6f}")
        print(f"   Limit: {result.get('limit', 0):.6f}")
        print(f"   Status: {'✅ Active' if result.get('is_active') else '⏳ Pending'}")
        print("=" * 60)

    # ============================================================
    # TOKEN - COMMANDS
    # ============================================================

    def cmd_send_token(self, args: List[str]):
        """Send a token (non-XRP) from issuer to receiver"""
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
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
            print_red("❌ Specify --to, --token and --amount")
            print("Example: send-token --to r... --token Arg0 --amount 1000")
            return
        
        if not issuer:
            issuer = manager.get_address()
            print_yellow(f"📌 Using issuer: {issuer} (current wallet)")
        
        print(f"\n📤 Sending token {token} from {manager.get_address()} to {to_address}")
        print(f"   Issuer: {issuer}")
        print(f"   Amount: {amount}")
        print("=" * 60)
        
        confirm = input("   Confirm? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Cancelled.")
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
            
            print(f"📡 Sending transaction...")
            tx = autofill(payment, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)
            
            tx_hash = response.result.get("hash", "unknown")
            
            print_green(f"\n✅ {amount} {token} sent successfully!")
            print(f"   Hash: {tx_hash}")
            print(f"   From: {wallet.classic_address}")
            print(f"   To: {to_address}")
            print(f"   Issuer: {issuer}")
            
        except Exception as e:
            print_red(f"❌ Error: {e}")

    def cmd_receive_token(self, args: List[str]):
        """Show how to receive a token (create trustline)"""
        if not self.wallet:
            self.init()
        
        manager = self.wallet._xrp_manager
        
        if not manager.is_loaded():
            print_red("❌ No wallet loaded!")
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
            print_red("❌ Specify --token and --issuer")
            print("Example: receive-token --token Arg0 --issuer r... --limit 1000000")
            return
        
        if not limit:
            limit = 1000000.0
        
        print_bold(f"\n📥 RECEIVE TOKEN {token}")
        print("=" * 60)
        print(f"   Token: {token}")
        print(f"   Issuer: {issuer}")
        print(f"   Limit: {limit}")
        print("=" * 60)
        print("\n📋 To receive this token, you need to create a trustline:")
        print(f"   python3 wallet_cli.py trustline-set {token} {issuer} {limit}")
        print("\n💡 After creating the trustline, the issuer can send you tokens.")
        print("   Verify with: python3 wallet_cli.py trustlines --refresh")


    # ============================================================
    # RETICULUM - COMMANDS
    # ============================================================

    def cmd_reticulum(self, args: List[str]):
        """Manage Reticulum"""
        if not RETICULUM_AVAILABLE:
            print_red("❌ Reticulum not available")
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
                print(f"❌ Unknown subcommand: {args[1]}")
        elif subcmd == "wallet" and len(args) > 1:
            if args[1] == "start":
                self._reticulum_wallet_start()
            elif args[1] == "stop":
                self._reticulum_wallet_stop()
            elif args[1] == "status":
                self._reticulum_wallet_status()
            else:
                print(f"❌ Unknown subcommand: {args[1]}")
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
            print(f"❌ Unknown command: {subcmd}")

    def _reticulum_wallet_start(self):
        """Start the wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        status = self.reticulum.get_status()
        if status.get('is_wallet', False):
            print_yellow(f"⚠️ Wallet already running")
            return
        
        print_blue("📡 Starting Reticulum wallet...")
        self.reticulum.start_wallet(blocking=False)
        
        time.sleep(1)
        status = self.reticulum.get_status()
        if status.get('is_wallet', False):
            print_green(f"✅ Wallet started")
            print_yellow(f"   Wallet Name: {status.get('wallet_name', 'Wallet')}")
            print_yellow(f"   Wallet Hash: {status.get('wallet_address', 'N/A')}")
        else:
            print_red("❌ Error starting wallet")

    def _reticulum_wallet_stop(self):
        """Stop the wallet"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        self.reticulum.stop_wallet()
        print_green("✅ Wallet stopped")

    def _reticulum_wallet_status(self):
        """Show wallet status"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        status = self.reticulum.get_status()
        print_bold("\n📊 WALLET STATUS")
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
        print("Reticulum commands:")
        print("  reticulum init          - Initialize Reticulum (already done at startup)")
        print("  reticulum gateway start - Start gateway")
        print("  reticulum gateway stop  - Stop gateway")
        print("  reticulum gateway status - Gateway status")
        print("  reticulum discover      - Discover gateways")
        print("  reticulum discover-wallets - Discover wallets")
        print("  reticulum peers         - Show peers with metrics")
        print("  reticulum best ASSET    - Best gateway for asset")
        print("  reticulum send ...      - Send transaction via Reticulum")

    def _reticulum_init(self):
        """Initialize Reticulum (already done at startup, useful for reset)"""
        if not self.reticulum_initialized:
            self._init_reticulum()
        else:
            print_yellow("⚠️ Reticulum already initialized")
        
        if self.reticulum:
            status = self.reticulum.get_status()
            print_green("📡 Reticulum Status:")
            print(f"   Gateway Address: {status.get('gateway_address', 'N/A')}")
            print(f"   Wallet Address: {status.get('wallet_address', 'N/A')}")
            print(f"   Cache size: {status.get('cache_size', 0)}")
            if status.get('is_gateway', False):
                print(f"   Gateway Running: ✅ Yes (PID: {status.get('pid')})")
            else:
                print(f"   Gateway Running: ❌ No")

    def _reticulum_gateway_start(self):
        """Start the gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        status = self.reticulum.get_status()
        if status.get('is_gateway', False):
            print_yellow(f"⚠️ Gateway already running (PID: {status.get('pid')})")
            return
        
        print_blue("📡 Starting Reticulum gateway...")
        self.reticulum.start_gateway(blocking=False)
        
        time.sleep(1)
        status = self.reticulum.get_status()
        if status.get('is_gateway', False):
            print_green(f"✅ Gateway started (PID: {status.get('pid')})")
            print_yellow(f"   Gateway Name: {status.get('gateway_name', 'Gateway')}")
            print_yellow(f"   Gateway Hash: {status.get('gateway_address', 'N/A')}")
        else:
            print_red("❌ Error starting gateway")

    def _reticulum_gateway_stop(self):
        """Stop the gateway"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        self.reticulum.stop_gateway()
        print_green("✅ Gateway stopped")

    def _reticulum_gateway_status(self):
        """Show gateway status"""
        if not self.reticulum:
            print_red("❌ Reticulum not initialized")
            return
        
        status = self.reticulum.get_status()
        print_bold("\n📊 GATEWAY STATUS")
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
        # INTERNET STATUS - CONFIGURATION AND REAL
        # ============================================================
        use_internet = status.get('use_internet', False)
        has_internet = status.get('has_internet', False)
        print(f"\n   🌐 INTERNET:")
        print(f"      Config:        {'ON' if use_internet else 'OFF'}")
        print(f"      Connection:    {'✅' if has_internet else '❌'}")
        
        # Ledger latencies
        xrp_reachable = status.get('xrp_reachable', False)
        xrp_latency = status.get('xrp_latency_ms')
        stellar_reachable = status.get('stellar_reachable', False)
        stellar_latency = status.get('stellar_latency_ms')
        
        print(f"\n   📊 LEDGER:")
        print(f"      XRP:          {'✅' if xrp_reachable else '❌'} {xrp_latency}ms" if xrp_latency else f"      XRP:          {'✅' if xrp_reachable else '❌'}")
        print(f"      Stellar:      {'✅' if stellar_reachable else '❌'} {stellar_latency}ms" if stellar_latency else f"      Stellar:      {'✅' if stellar_reachable else '❌'}")
        
        print("=" * 60)

    def _reticulum_discover(self):
        """Cerca gateway - mostra TUTTI quelli in cache con first_seen e last_seen"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        print_blue("🔍 Ricerca gateway Reticulum...")
        
        # Ottieni gateway dalla cache (TUTTI, non solo quelli attivi)
        gateways = self.reticulum.discover_gateways()
        
        print_bold(f"\n🔍 GATEWAY TROVATI ({len(gateways)})")
        print("=" * 100)
        
        if gateways:
            print(f"{'Nome':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
            print("-" * 100)
            
            for gw in gateways:
                name = gw.get('name', 'Sconosciuto')[:18]
                gw_id = gw.get('gateway_id', '?')
                first_seen = gw.get('first_seen')
                last_seen = gw.get('last_seen')
                
                first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Mai'
                last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Mai'
                hops = gw.get('hops', '?')
                
                print(f"{name:<20} {gw_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
            
            print("=" * 100)
            print(f"Totale: {len(gateways)} gateway in cache")
        else:
            print("   ❌ Nessun gateway trovato in cache")
        print("=" * 100)

    def _reticulum_discover_wallets(self):
        """Cerca wallet - mostra TUTTI quelli in cache con first_seen e last_seen"""
        if not self.reticulum:
            print_red("❌ Reticulum non inizializzato")
            return
        
        print_blue("🔍 Ricerca wallet Reticulum...")
        
        # Ottieni wallet dalla cache (TUTTI, non solo quelli attivi)
        wallets = self.reticulum.discover_wallets()
        
        print_bold(f"\n🔍 WALLET TROVATI ({len(wallets)})")
        print("=" * 100)
        
        if wallets:
            print(f"{'Nome':<20} {'Hash':<36} {'First Seen':<20} {'Last Seen':<20} {'Hops':<6}")
            print("-" * 100)
            
            for w in wallets:
                name = w.get('name', 'Sconosciuto')[:18]
                w_id = w.get('wallet_id', '?')
                first_seen = w.get('first_seen')
                last_seen = w.get('last_seen')
                
                first_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first_seen)) if first_seen else 'Mai'
                last_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else 'Mai'
                hops = w.get('hops', '?')
                
                print(f"{name:<20} {w_id:<36} {first_str:<20} {last_str:<20} {hops:<6}")
            
            print("=" * 100)
            print(f"Totale: {len(wallets)} wallet in cache")
        else:
            print("   ❌ Nessun wallet trovato in cache")
        print("=" * 100)

    def _reticulum_peers(self):
        if not self.metrics:
            print_red("❌ Metriche non disponibili")
            return
        
        peers = self.metrics.get_all_peers()
        
        if not peers:
            print_yellow("⚠️ Nessun peer conosciuto")
            return
        
        # ============================================================
        # CALCOLA PUNTEGGIO PERFORMANCE
        # ============================================================
        def calculate_score(p):
            score = 0.0
            
            # Affidabilità (Rel) - peso 40
            rel = p.get('reliability', 0)
            score += rel * 40
            
            # Reputazione - peso 0.3
            rep = p.get('reputation', 50)
            score += rep * 0.3
            
            # Latenza RTT (minore è meglio)
            latency = p.get('latency_ms')
            if latency and latency > 0:
                if latency < 50:
                    score += 15
                elif latency < 100:
                    score += 10
                elif latency < 200:
                    score += 5
                elif latency < 500:
                    score -= 5
                else:
                    score -= 15
            
            # Hops (meno hop = meglio)
            hops = p.get('hops')
            if hops:
                if hops == 1:
                    score += 10
                elif hops == 2:
                    score += 5
                elif hops == 3:
                    score += 0
                else:
                    score -= hops * 2
            
            # XRP raggiungibile
            if p.get('xrp_reachable'):
                score += 5
                xrp_lat = p.get('xrp_latency_ms')
                if xrp_lat and xrp_lat < 200:
                    score += 5
                elif xrp_lat and xrp_lat < 500:
                    score += 2
            
            # Stellar raggiungibile
            if p.get('stellar_reachable'):
                score += 5
                stellar_lat = p.get('stellar_latency_ms')
                if stellar_lat and stellar_lat < 200:
                    score += 5
                elif stellar_lat and stellar_lat < 500:
                    score += 2
            
            # Internet
            if p.get('has_internet'):
                score += 3
            
            # RSSI (se disponibile)
            rssi = p.get('rssi')
            if rssi is not None:
                if rssi > -60:
                    score += 5
                elif rssi > -80:
                    score += 2
                elif rssi < -100:
                    score -= 5
            
            return max(0, min(100, score))
        
        # ============================================================
        # ORDINA PER PUNTEGGIO (dal migliore al peggiore)
        # ============================================================
        peers_sorted = sorted(peers, key=calculate_score, reverse=True)
        
        # ============================================================
        # VERIFICA SE CI SONO DATI RADIO
        # ============================================================
        has_radio = any(p.get('rssi') is not None or p.get('snr') is not None for p in peers)
        
        # ============================================================
        # STAMPA CON RADIO
        # ============================================================
        if has_radio:
            print_bold(f"\n🔍 PEER ORDINATI PER PERFORMANCE ({len(peers_sorted)})")
            print("=" * 260)
            print(f"{'#':<3} {'Nome':<14} {'Score':<6} {'Rel':<6} {'Rep':<4} {'Hops':<5} {'RTT':<8} {'RSSI':<10} {'SNR':<10} {'XRP':<14} {'Stellar':<14} {'Internet':<9} {'Ultimo visto':<15} {'ID':<36} {'Assets'}")
            print("-" * 260)
            
            for idx, p in enumerate(peers_sorted, 1):
                sc = calculate_score(p)
                name = str(p.get('name', 'UNKNOWN'))[:12]
                rel = p.get('reliability', 0)
                rep = p.get('reputation', 50)
                hops = str(p.get('hops', '?'))
                rtt = f"{p.get('latency_ms', '?')}ms"
                
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
                if p.get('xrp_reachable'):
                    xrp_lat = p.get('xrp_latency_ms')
                    xrp_str = f"✅{xrp_lat}ms" if xrp_lat else "✅ OK"
                else:
                    xrp_str = "❌"
                
                # Stellar
                if p.get('stellar_reachable'):
                    stellar_lat = p.get('stellar_latency_ms')
                    stellar_str = f"✅{stellar_lat}ms" if stellar_lat else "✅ OK"
                else:
                    stellar_str = "❌"
                
                internet = "🌐" if p.get('has_internet') else "📡"
                last_seen = self._format_time_ago(p.get('last_seen'))
                gw_id = p.get('gateway_id', 'N/A')
                
                assets = p.get('assets', [])
                if isinstance(assets, list):
                    assets_str = ', '.join(assets[:3])
                    if len(assets) > 3:
                        assets_str += f" +{len(assets)-3}"
                else:
                    assets_str = str(assets)[:20]
                
                # Colori
                sc_color = Colors.GREEN if sc > 70 else Colors.YELLOW if sc > 40 else Colors.RED
                rel_color = Colors.GREEN if rel > 0.9 else Colors.YELLOW if rel > 0.7 else Colors.RED
                
                print(f"{idx:<3} {name:<14} {sc_color}{sc:5.0f}{Colors.RESET} {rel_color}{rel:5.2f}{Colors.RESET} {rep:<4} {hops:<5} {rtt:<8} {rssi_str:<10} {snr_str:<10} {xrp_str:<14} {stellar_str:<14} {internet:<9} {last_seen:<15} {gw_id:<36} {assets_str}")
        
        # ============================================================
        # STAMPA SENZA RADIO
        # ============================================================
        else:
            print_bold(f"\n🔍 PEER ORDINATI PER PERFORMANCE ({len(peers_sorted)})")
            print("=" * 230)
            print(f"{'#':<3} {'Nome':<16} {'Score':<6} {'Rel':<6} {'Rep':<4} {'Hops':<5} {'RTT':<8} {'XRP':<14} {'Stellar':<14} {'Internet':<9} {'Ultimo visto':<15} {'ID':<36} {'Assets'}")
            print("-" * 230)
            
            for idx, p in enumerate(peers_sorted, 1):
                sc = calculate_score(p)
                name = str(p.get('name', 'UNKNOWN'))[:14]
                rel = p.get('reliability', 0)
                rep = p.get('reputation', 50)
                hops = str(p.get('hops', '?'))
                rtt = f"{p.get('latency_ms', '?')}ms"
                
                # XRP
                if p.get('xrp_reachable'):
                    xrp_lat = p.get('xrp_latency_ms')
                    xrp_str = f"✅{xrp_lat}ms" if xrp_lat else "✅ OK"
                else:
                    xrp_str = "❌"
                
                # Stellar
                if p.get('stellar_reachable'):
                    stellar_lat = p.get('stellar_latency_ms')
                    stellar_str = f"✅{stellar_lat}ms" if stellar_lat else "✅ OK"
                else:
                    stellar_str = "❌"
                
                internet = "🌐" if p.get('has_internet') else "📡"
                last_seen = self._format_time_ago(p.get('last_seen'))
                gw_id = p.get('gateway_id', 'N/A')
                
                assets = p.get('assets', [])
                if isinstance(assets, list):
                    assets_str = ', '.join(assets[:3])
                    if len(assets) > 3:
                        assets_str += f" +{len(assets)-3}"
                else:
                    assets_str = str(assets)[:20]
                
                # Colori
                sc_color = Colors.GREEN if sc > 70 else Colors.YELLOW if sc > 40 else Colors.RED
                rel_color = Colors.GREEN if rel > 0.9 else Colors.YELLOW if rel > 0.7 else Colors.RED
                
                print(f"{idx:<3} {name:<16} {sc_color}{sc:5.0f}{Colors.RESET} {rel_color}{rel:5.2f}{Colors.RESET} {rep:<4} {hops:<5} {rtt:<8} {xrp_str:<14} {stellar_str:<14} {internet:<9} {last_seen:<15} {gw_id:<36} {assets_str}")
        
        # ============================================================
        # LINEA FINALE
        # ============================================================
        print("=" * (260 if has_radio else 230))
        
        # ============================================================
        # STATISTICHE
        # ============================================================
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
        
        # ============================================================
        # MIGLIOR PEER
        # ============================================================
        if peers_sorted:
            b = peers_sorted[0]
            best_score = calculate_score(b)
            print(f"\n🏆 MIGLIOR PEER: {b.get('name', 'UNKNOWN')}")
            print(f"   Score: {best_score:.0f} | Rel: {b.get('reliability', 0):.2f} | Rep: {b.get('reputation', 50)}")
            print(f"   Gateway ID: {b.get('gateway_id', 'N/A')}")
            print(f"   RTT Reticulum: {b.get('latency_ms', '?')}ms | Hops: {b.get('hops', '?')}")
            print(f"   XRP: {'✅' if b.get('xrp_reachable') else '❌'} ({b.get('xrp_latency_ms', '?')}ms)")
            print(f"   Stellar: {'✅' if b.get('stellar_reachable') else '❌'} ({b.get('stellar_latency_ms', '?')}ms)")
            print(f"   Internet: {'✅' if b.get('has_internet') else '❌'}")
            if b.get('assets'):
                print(f"   Assets: {', '.join(b.get('assets', []))}")
            rssi = b.get('rssi')
            if rssi is not None:
                print(f"   RSSI: {rssi:.1f}dBm")
            snr = b.get('snr')
            if snr is not None:
                print(f"   SNR: {snr:.1f}dB")

    def _reticulum_best_gateway(self, asset: str):
        """Show the best gateway for an asset"""
        if not self.metrics:
            print_red("❌ Metrics not available")
            return
        
        if not asset:
            print_red("❌ Specify an asset (e.g. RLUSD)")
            return
        
        best = self.metrics.get_best_gateway(asset)
        
        if best:
            print_green(f"\n✅ Best gateway for {asset}:")
            print(f"   Name: {best.get('name', 'UNKNOWN')}")
            print(f"   ID: {best.get('gateway_id', 'N/A')}")
            print(f"   Hops: {best.get('hops', '?')}")
            print(f"   RTT Reticulum: {best.get('latency_ms', '?')}ms")
            
            # Ledger latencies
            xrp_latency = best.get('xrp_latency_ms')
            xrp_reachable = best.get('xrp_reachable', False)
            stellar_latency = best.get('stellar_latency_ms')
            stellar_reachable = best.get('stellar_reachable', False)
            
            print(f"   XRP: {'✅' if xrp_reachable else '❌'} {xrp_latency}ms" if xrp_latency else f"   XRP: {'✅' if xrp_reachable else '❌'}")
            print(f"   Stellar: {'✅' if stellar_reachable else '❌'} {stellar_latency}ms" if stellar_latency else f"   Stellar: {'✅' if stellar_reachable else '❌'}")
            
            # Radio metrics
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
            print_red(f"❌ No gateway found for {asset}")

    def _reticulum_send(self, args: List[str]):
        """Invia transazione via Reticulum - CON VALIDAZIONE"""
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

        # Estrai parametri dagli argomenti
        for i, arg in enumerate(args):
            if arg == "--to" and i + 1 < len(args):
                to_addr = args[i + 1].strip()
            elif arg == "--amount" and i + 1 < len(args):
                try:
                    amount = float(args[i + 1])
                except:
                    pass
            elif arg == "--asset" and i + 1 < len(args):
                asset = args[i + 1]
            elif arg == "--gateway" and i + 1 < len(args):
                gateway_id = args[i + 1]

        # VALIDA INDIRIZZO
        if not to_addr:
            print_red("❌ Indirizzo destinatario non valido")
            return
        if len(to_addr) < 20:
            print_red("❌ Indirizzo troppo corto (minimo 20 caratteri)")
            return

        # VALIDA AMMONTARE
        if not amount or amount <= 0:
            print_red("❌ Ammontare non valido (deve essere > 0)")
            return

        # CERCA GATEWAY
        if not gateway_id:
            print_blue("🔍 Cerco gateway disponibili...")
            gateways = self.reticulum.discover_gateways()
            if not gateways:
                print_red("❌ Nessun gateway disponibile")
                return
            # Mostra gateway disponibili
            print_blue(f"📡 Gateway disponibili: {len(gateways)}")
            for i, gw in enumerate(gateways[:5], 1):
                name = gw.get('name', 'UNKNOWN')
                gw_id = gw.get('gateway_id', '?')
                print(f"   {i}) {name} ({gw_id[:16]}...)")
            if len(gateways) > 5:
                print(f"   ... e altri {len(gateways)-5}")
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
        """Request info from a specific gateway"""
        if not self.metrics:
            print_red("❌ Metrics not available")
            return
        
        print_blue("🔍 Available gateways:")
        gateways = self.reticulum.discover_gateways()
        if not gateways:
            print_red("❌ No gateways found")
            return
        
        # Filter out own gateway
        my_id = self.reticulum.gateway_address
        filtered = [g for g in gateways if g.get('gateway_id') != my_id]
        
        if not filtered:
            print_yellow("⚠️ Only your own gateway found, no peers available")
            return
        
        for i, gw in enumerate(filtered, 1):
            name = gw.get('name', 'UNKNOWN')
            gw_id = gw.get('gateway_id', '?')
            hops = gw.get('hops', '?')
            rssi = gw.get('rssi')
            rssi_str = f" RSSI:{rssi:.1f}dBm" if rssi is not None else ""
            print(f"   {i}) {name} ({gw_id[:16]}...) Hops:{hops}{rssi_str}")
        
        try:
            choice = int(input("\nSelect gateway (number): ").strip())
            if 1 <= choice <= len(filtered):
                gateway_id = filtered[choice - 1].get('gateway_id')
                if gateway_id:
                    print_blue(f"📡 Requesting info from {gateway_id[:16]}...")
                    success = self.metrics.request_gateway_info(gateway_id)
                    if success:
                        print_green("✅ Request sent and response received!")
                        # ============================================================
                        # SHOW ONLY THE JUST INTERROGATED PEER
                        # ============================================================
                        self._show_single_peer(gateway_id)
                    else:
                        print_red("❌ Error in request (see log above)")
            else:
                print_red("❌ Invalid choice")
        except ValueError:
            print_red("❌ Enter a valid number")


    def _show_single_peer(self, gateway_id: str):
        """Show a single peer in table format"""
        if not self.metrics:
            print_red("❌ Metrics not available")
            return
        
        peers = self.metrics.get_all_peers()
        peer = None
        for p in peers:
            if p.get('gateway_id') == gateway_id:
                peer = p
                break
        
        if not peer:
            print_yellow("⚠️ Peer not found in database")
            return
        
        # Show in table format (style _reticulum_peers but for a single peer)
        print_bold(f"\n🔍 PEER: {peer.get('name', 'UNKNOWN')}")
        print("=" * 120)
        print(f"{'ID':<38} {'Hops':<6} {'RTT':<10} {'XRP':<14} {'Stellar':<14} {'Rep':<5} {'Internet':<9} {'Last seen':<15}")
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
        
        # Show Assets
        assets = peer.get('assets', [])
        if isinstance(assets, list) and assets:
            print(f"   Assets: {', '.join(assets)}")
        
        # Show Fee
        fee = peer.get('fee', 'N/A')
        fee_asset = peer.get('fee_asset', '')
        if fee != 'N/A':
            print(f"   Fee: {fee} {fee_asset}")


# ============================================================
# 6. INTERACTIVE MODE
# ============================================================

def interactive_mode():
    """Interactive mode with Reticulum always active"""
    cli = WalletCLI()
    cli.init()
    cli._interactive_mode = True
    
    print_bold("\n" + "=" * 60)
    print_bold("    💰 WALLET CLI - INTERACTIVE MODE")
    print_bold("=" * 60)
    print("")
    print_green("📡 Reticulum active for the entire session")
    
    try:
        while True:
            print("\n" + "-" * 40)
            print("  1) Wallet")
            print("  2) Show balance")
            print("  3) Show address")
            print("  4) Derive addresses")
            print("  5) Send payment")
            print("  6) Wallet info")
            print("  7) History")
            print("  8) Fund testnet (XLM)")
            print("  9) Export")
            print(" 10) Trustline")
            print(" 11) Send token")
            print(" 12) Reticulum")
            print("  0) Exit")
            
            # Show Reticulum status
            if cli.reticulum:
                status = cli.reticulum.get_status()
                if status.get('is_gateway', False):
                    print_yellow(f"  📡 Gateway active (PID: {status.get('pid')})")
                elif status.get('is_wallet', False):
                    print_yellow(f"  📡 Wallet active (PID: {status.get('pid')})")
                elif status.get('running', False):
                    print_cyan("  📡 Reticulum active")
                else:
                    print_red("  ❌ Reticulum not active")
            print("-" * 40)
            
            choice = input("\nChoice: ").strip()
            
            if choice == '0':
                print_green("👋 Goodbye!")
                break
            
            # ============================================================
            # 1) WALLET - SUBMENU
            # ============================================================
            elif choice == '1':
                while True:
                    # Show active wallet and list
                    active = cli._get_active_wallet_name()
                    wallets = cli._get_wallet_list()
                    
                    print("\n" + "=" * 50)
                    print("  📂 WALLET")
                    print("=" * 50)
                    print(f"  Active wallet: {active or 'NONE'}")
                    print("\n  📋 Lista wallet:")
                    if wallets:
                        for i, w in enumerate(wallets, 1):
                            marker = "▶" if w["name"] == active else " "
                            address = w.get('address', 'unknown')
                            print(f"    {i}. {marker} {w['name']:<15} ({w.get('crypto', 'XRP')} - {w.get('network', 'testnet')}) {address}")
                    else:
                        print("    ❌ Nessun wallet salvato")
                    
                    print("\n" + "-" * 50)
                    print("  1) Create wallet")
                    print("  2) Import wallet")
                    print("  3) Remove wallet")
                    print("  4) Switch wallet")
                    print("  0) Back to main menu")
                    print("-" * 50)
                    
                    sub = input("\nChoice: ").strip()
                    
                    if sub == '0':
                        break
                    elif sub == '1':
                        name = input("Name (default): ").strip() or "default"
                        crypto = input("Crypto (XRP/XLM): ").strip().upper() or "XRP"
                        network = input("Network (testnet/mainnet): ").strip().lower() or "testnet"
                        cli.cmd_create(name, crypto, network)
                    elif sub == '2':
                        seed = input("Enter seed/mnemonic/numbers: ").strip()
                        if seed:
                            name = input("Name (imported): ").strip() or "imported"
                            crypto = input("Crypto (auto/XRP/XLM): ").strip().upper() or "auto"
                            network = input("Network (testnet/mainnet): ").strip().lower() or "testnet"
                            cli.cmd_import(seed, name, crypto, network)
                    elif sub == '3':
                        cli.cmd_remove_wallet()
                    elif sub == '4':
                        name = input("Wallet name: ").strip()
                        if name:
                            cli.cmd_switch(name)
                    else:
                        print_red("❌ Invalid choice")
            
            # ============================================================
            # 2) SHOW BALANCE
            # ============================================================
            elif choice == '2':
                cli.cmd_balance(True)
            
            # ============================================================
            # 3) SHOW ADDRESS
            # ============================================================
            elif choice == '3':
                cli.cmd_address()
            
            # ============================================================
            # 4) DERIVE ADDRESSES
            # ============================================================
            elif choice == '4':
                keyword = input("Keyword (default): ").strip() or "default"
                count = int(input("Count (5): ").strip() or "5")
                cli.cmd_derive(keyword, count)
            
            # ============================================================
            # 5) SEND PAYMENT
            # ============================================================
            elif choice == '5':
                to_addr = input("Destination address: ").strip()
                try:
                    amount = float(input("Amount: ").strip())
                except ValueError:
                    print_red("❌ Invalid amount")
                    continue
                memo = input("Memo: ").strip()
                if to_addr and amount > 0:
                    cli.cmd_send(to_addr, amount, memo)
                else:
                    print_red("❌ Invalid data")
            
            # ============================================================
            # 6) WALLET INFO
            # ============================================================
            elif choice == '6':
                cli.cmd_info()
            
            # ============================================================
            # 7) HISTORY
            # ============================================================
            elif choice == '7':
                limit = int(input("Number of transactions (10): ").strip() or "10")
                cli.cmd_history(limit)
            
            # ============================================================
            # 8) FUND TESTNET
            # ============================================================
            elif choice == '8':
                cli.cmd_fund_testnet()
            
            # ============================================================
            # 9) EXPORT
            # ============================================================
            elif choice == '9':
                private = input("Include private key? (y/N): ").strip().lower() == 'y'
                cli.cmd_export(private)
            
            # ============================================================
            # 10) TRUSTLINE
            # ============================================================
            elif choice == '10':
                print("\n🔗 TRUSTLINE MANAGEMENT")
                print("  1) Show trustlines")
                print("  2) Create trustline")
                print("  3) Remove trustline")
                print("  4) Trustline info")
                sub = input("Choice: ").strip()
                if sub == '1':
                    cli.cmd_trustlines(["--refresh"])
                elif sub == '2':
                    asset = input("Asset (e.g. RLUSD): ").strip()
                    issuer = input("Issuer address: ").strip()
                    limit = input("Limit (0 to remove): ").strip()
                    args = [asset, issuer]
                    if limit:
                        args.append(limit)
                    else:
                        args.append("0")
                    cli.cmd_trustline_set(args)
                elif sub == '3':
                    asset = input("Asset: ").strip()
                    issuer = input("Issuer address: ").strip()
                    cli.cmd_trustline_remove([asset, issuer])
                elif sub == '4':
                    asset = input("Asset: ").strip()
                    issuer = input("Issuer (optional): ").strip()
                    cli.cmd_trustline_info([asset] + ([issuer] if issuer else []))
            
            # ============================================================
            # 11) SEND TOKEN
            # ============================================================
            elif choice == '11':
                to_addr = input("Destination address: ").strip()
                token = input("Token name (e.g. Arg0): ").strip()
                try:
                    amount = float(input("Amount: ").strip())
                except ValueError:
                    print_red("❌ Invalid amount")
                    continue
                issuer = input("Issuer (optional, sends from current wallet): ").strip()
                if to_addr and token and amount:
                    args = ["--to", to_addr, "--token", token, "--amount", str(amount)]
                    if issuer:
                        args += ["--issuer", issuer]
                    cli.cmd_send_token(args)
                else:
                    print_red("❌ Invalid data")
            
            # ============================================================
            # 12) RETICULUM - SUBMENU
            # ============================================================
            elif choice == '12':
                while True:
                    print("\n" + "=" * 50)
                    print("  📡 RETICULUM")
                    print("=" * 50)
                    
                    if cli.reticulum:
                        status = cli.reticulum.get_status()
                        gw_status = "✅ Active" if status.get('is_gateway') else "❌ Stopped"
                        peers = cli.metrics.get_all_peers() if cli.metrics else []
                        print(f"\n  Gateway: {gw_status}")
                        print(f"  Known peers: {len(peers)}")
                    
                    print("\n" + "-" * 50)
                    print("  1) Gateway status")
                    print("  2) Start gateway")
                    print("  3) Stop gateway")
                    print("  4) Discover gateways")
                    print("  5) Discover wallets")
                    print("  6) Peer metrics")
                    print("  7) Best gateway")
                    print("  8) Request gateway info")
                    print("  9) Send transaction")
                    print(" 10) Test all gateways")
                    print("  0) Back to main menu")
                    print("-" * 50)
                    
                    sub = input("\nChoice: ").strip()
                    
                    if sub == '0':
                        break
                    elif sub == '1':
                        cli._reticulum_gateway_status()
                    elif sub == '2':
                        cli._reticulum_gateway_start()
                    elif sub == '3':
                        cli._reticulum_gateway_stop()
                    elif sub == '4':
                        cli._reticulum_discover()
                    elif sub == '5':
                        cli._reticulum_discover_wallets()
                    elif sub == '6':
                        cli._reticulum_peers()
                    elif sub == '7':
                        asset = input("Asset (e.g. RLUSD): ").strip()
                        if asset:
                            cli._reticulum_best_gateway(asset)
                        else:
                            print_red("❌ Specify an asset")
                    elif sub == '8':
                        cli._reticulum_request_info()
                    elif sub == '9':
                        to_addr = input("Destination address: ").strip()
                        if len(to_addr) < 20:
                            print_red("❌ Address too short (minimum 20 characters)")
                        else:
                            try:
                                amount = float(input("Amount: ").strip())
                                if amount <= 0:
                                    print_red("❌ Amount must be greater than 0")
                                else:
                                    asset = input("Asset (XRP): ").strip() or "XRP"
                                    cli._reticulum_send(["--to", to_addr, "--amount", str(amount), "--asset", asset])
                            except ValueError:
                                print_red("❌ Invalid amount")
                    elif sub == '10':
                        cli.cmd_test_gateways()
                    else:
                        print_red("❌ Invalid choice")
            
            else:
                print_red("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n")
        print_yellow("⚠️ Interrupted by user")
    
    finally:
        # Stop metrics
        if hasattr(cli, 'metrics') and cli.metrics:
            try:
                cli.metrics.stop_query_loop()
            except:
                pass
        
        # Stop gateway if active
        if cli.reticulum:
            status = cli.reticulum.get_status()
            if status.get('is_gateway', False):
                print("\n🛑 Stopping gateway...")
                cli.reticulum.stop_gateway()
            print_green("👋 Goodbye!")


# ============================================================
# 5. MAIN
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="PAX Wallet CLI - XRP/XLM wallet management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Interactive mode (RECOMMENDED for Reticulum)
  python paxwallet.py interactive
  
  # Create wallet
  python paxwallet.py create --name my_wallet --crypto XRP --network testnet
  
  # Import mnemonic
  python paxwallet.py import --seed "abandon abandon ..." --name my_wallet
  
  # Balance
  python paxwallet.py balance
  
  # Info
  python paxwallet.py info
  
  # History
  python paxwallet.py history --limit 10
  
  # Send XRP
  python paxwallet.py send --to r... --amount 1.5 --memo "test"
  
  # Send Token
  python paxwallet.py send-token --to r... --token Arg0 --amount 1000
  
  # Receive Token
  python paxwallet.py receive-token --token Arg0 --issuer r... --limit 1000000
  
  # List wallets
  python paxwallet.py list-wallets
  
  # Switch wallet
  python paxwallet.py switch my_wallet
  
  # Trustline
  python paxwallet.py trustlines --refresh
  python paxwallet.py trustline-set RLUSD rHb9CJAWyB4rj91VRwn96DkukG4bwdtyth 10000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    create_parser = subparsers.add_parser('create', help='Create a new wallet')
    create_parser.add_argument('--name', default='default', help='Wallet name')
    create_parser.add_argument('--crypto', default='XRP', choices=['XRP', 'XLM'], help='Crypto')
    create_parser.add_argument('--network', default='testnet', choices=['testnet', 'mainnet', 'devnet'], help='Network')
    
    import_parser = subparsers.add_parser('import', help='Import a wallet')
    import_parser.add_argument('--seed', required=True, help='Seed, mnemonic or Xaman numbers')
    import_parser.add_argument('--name', default='imported', help='Wallet name')
    import_parser.add_argument('--crypto', default='auto', choices=['auto', 'XRP', 'XLM'], help='Crypto')
    import_parser.add_argument('--network', default='testnet', choices=['testnet', 'mainnet', 'devnet'], help='Network')
    
    balance_parser = subparsers.add_parser('balance', help='Show balance')
    balance_parser.add_argument('--refresh', action='store_true', help='Force refresh')
    
    subparsers.add_parser('address', help='Show address')
    
    derive_parser = subparsers.add_parser('derive', help='Derive addresses')
    derive_parser.add_argument('--keyword', default='default', help='Derivation keyword')
    derive_parser.add_argument('--count', type=int, default=5, help='Number of addresses')
    
    send_parser = subparsers.add_parser('send', help='Send payment')
    send_parser.add_argument('--to', required=True, help='Destination address')
    send_parser.add_argument('--amount', required=True, type=float, help='Amount')
    send_parser.add_argument('--memo', default='', help='Memo')
    
    subparsers.add_parser('info', help='Show wallet info')
    
    history_parser = subparsers.add_parser('history', help='Show history')
    history_parser.add_argument('--limit', type=int, default=10, help='Number of transactions')
    
    subparsers.add_parser('fund', help='Fund wallet on testnet (XLM only)')
    
    export_parser = subparsers.add_parser('export', help='Export wallet')
    export_parser.add_argument('--private', action='store_true', help='Include private key')
    
    subparsers.add_parser('list-wallets', help='List all saved wallets')
    
    switch_parser = subparsers.add_parser('switch', help='Switch active wallet')
    switch_parser.add_argument('name', help='Wallet name')
    
    wallet_parser = subparsers.add_parser('wallet', help='Create or switch wallet')
    wallet_parser.add_argument('name', nargs='?', default=None, help='Wallet name')
    
    subparsers.add_parser('interactive', help='Interactive mode')
    
    # ============================================================
    # TRUSTLINE - COMMANDS
    # ============================================================

    trustlines_parser = subparsers.add_parser('trustlines', help='Show trustlines')
    trustlines_parser.add_argument('--refresh', '-r', action='store_true', help='Force refresh')

    trustline_set_parser = subparsers.add_parser('trustline-set', help='Create trustline')
    trustline_set_parser.add_argument('asset', help='Asset code (e.g. RLUSD)')
    trustline_set_parser.add_argument('issuer', help='Issuer address')
    trustline_set_parser.add_argument('limit', nargs='?', type=float, default=0, help='Limit (default: 0 = remove)')

    trustline_remove_parser = subparsers.add_parser('trustline-remove', help='Remove trustline')
    trustline_remove_parser.add_argument('asset', help='Asset code')
    trustline_remove_parser.add_argument('issuer', help='Issuer address')

    trustline_info_parser = subparsers.add_parser('trustline-info', help='Trustline info')
    trustline_info_parser.add_argument('asset', help='Asset code')
    trustline_info_parser.add_argument('issuer', nargs='?', help='Issuer address (optional)')

    # ============================================================
    # TOKEN - COMMANDS
    # ============================================================

    send_token_parser = subparsers.add_parser('send-token', help='Send a token (non-XRP)')
    send_token_parser.add_argument('--to', required=True, help='Destination address')
    send_token_parser.add_argument('--token', required=True, help='Token name (e.g. Arg0)')
    send_token_parser.add_argument('--amount', required=True, type=float, help='Amount to send')
    send_token_parser.add_argument('--issuer', help='Token issuer (default: current wallet)')

    receive_token_parser = subparsers.add_parser('receive-token', help='Prepare to receive a token')
    receive_token_parser.add_argument('--token', required=True, help='Token name')
    receive_token_parser.add_argument('--issuer', required=True, help='Issuer address')
    receive_token_parser.add_argument('--limit', type=float, default=1000000.0, help='Maximum limit')

    # ============================================================
    # RETICULUM - COMMANDS (REMOVED - USE INTERACTIVE)
    # ============================================================
    # Reticulum CLI commands are not supported anymore
    # Use interactive mode: python paxwallet.py interactive
    
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
    # If no arguments or just "interactive"
    if len(sys.argv) == 1:
        sys.argv.append("interactive")
    main()