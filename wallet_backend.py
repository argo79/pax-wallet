#!/usr/bin/env python3
"""
wallet_backend.py - Backend API per PAX Wallet
"""

import sys
import json
import re
import logging
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Tuple
import threading

# ============================================================
# VERSIONE
# ============================================================
VERSION = "0.10.2b"
__version__ = VERSION

# ============================================================
# COLORI PER OUTPUT (indipendenti)
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
# UTILITY CONDIVISE (ESPORTATE PER IL FRONTEND)
# ============================================================

def format_time_ago(timestamp: int) -> str:
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

def parse_tx_date(tx: Dict, tx_data: Dict) -> str:
    """Parsea la data da una transazione XRP."""
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
# PATCH PER RETICULUM
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

# ============================================================
# IMPORTA I MODULI CORE
# ============================================================

from core_wrapper import create_core, CoreWallet, get_core_path
from wallet_api import create_wallet, UnifiedWallet
from wallet_manager import HybridXRPManager, WalletInfo, CoreTrustlineInfo

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

try:
    from reticulum.gateway_metrics import GatewayMetrics
    METRICS_AVAILABLE = True
except ImportError as e:
    METRICS_AVAILABLE = False
    print(f"⚠️ Metriche non disponibili: {e}")

import colorama
colorama.init()

# ============================================================
# CLASSE BACKEND
# ============================================================

class WalletBackend:
    """
    Backend per PAX Wallet - INDIPENDENTE e COMPLETO
    Contiene TUTTA la logica che era in WalletCLI
    """
    
    def __init__(self, password: str = None):
        # Wallet state
        self.wallet: Optional[UnifiedWallet] = None
        self.data_file = "wallet_cli.db"
        self.wallets_dir = Path("wallets")
        self.wallets_dir.mkdir(exist_ok=True)
        self.active_wallet_name_file = Path("active_wallet.txt")
        self.rubrica_file = Path("rubrica.json")
        self._interactive_mode = False
        
        # Password
        self._wallet_password = password
        self._password_verified = bool(password)
        
        # Reticulum
        self.reticulum: Optional[ReticulumManager] = None
        self.reticulum_initialized = False
        self.reticulum_config = ReticulumConfig()
        
        # 🔥 LEGGI IL FLAG INTERNET DAL CONFIG
        self.use_internet = getattr(self.reticulum_config, 'use_internet', True)
        print_green(f"🌐 Modalità internet: {'ON' if self.use_internet else 'OFF (Reticulum)'}")

        # 🔥 LEGGI IL FLAG TOR DAL CONFIG
        self.use_tor = getattr(self.reticulum_config, 'use_tor', False)
        self.tor_socks_port = getattr(self.reticulum_config, 'tor_socks_port', 9050)
        self.tor_timeout_seconds = getattr(self.reticulum_config, 'tor_timeout_seconds', 30)

        if self.use_tor:
            print_blue(f"🧅 TOR attivo su localhost:{self.tor_socks_port}")
        else:
            print_green("🧅 TOR: OFF")
        
        self._update_proxy()

        # 🔥 PATCH PER COMPATIBILITÀ - USA IL VALORE DAL CONFIG!
        discover_since = getattr(self.reticulum_config, 'discover_since_seconds', 86400)
        
        if not hasattr(self.reticulum_config, 'gateway'):
            self.reticulum_config.gateway = type('obj', (object,), {'discover_since_seconds': discover_since})()
        if not hasattr(self.reticulum_config, 'wallet'):
            self.reticulum_config.wallet = type('obj', (object,), {'discover_since_seconds': discover_since})()
        
        self.metrics = None
        
        self._cached_wallet_list = None
        self._cached_wallet_list_time = 0
        self._cache_ttl = 2
        
        # Inizializza Reticulum
        if RETICULUM_AVAILABLE:
            self._init_reticulum()
    
    # ============================================================
    # RETICULUM - INIZIALIZZAZIONE
    # ============================================================
    
    def _init_reticulum(self):
        """Inizializza Reticulum UNA SOLA VOLTA"""
        if not RETICULUM_AVAILABLE:
            return
        
        if not self.reticulum_initialized:
            self.reticulum = ReticulumManager()
            
            if METRICS_AVAILABLE:
                try:
                    # 🔥 PASSA IL NOME DAL CONFIG A GatewayMetrics!
                    gateway_name = self.reticulum.config.gateway_name if hasattr(self.reticulum, 'config') else "Gateway"
                    self.metrics = GatewayMetrics(self.reticulum.identity, gateway_name=gateway_name)
                    self.metrics.set_my_gateway_id(self.reticulum.gateway_address)
                    
                    if hasattr(self.reticulum, 'config'):
                        self.metrics.set_use_internet(self.reticulum.config.use_internet)
                        self.metrics.set_ledger_timeout(self.reticulum.config.ledger_timeout_seconds)
                        self.metrics.set_ledger_check_interval(self.reticulum.config.ledger_check_interval)
                    
                    self.reticulum.set_metrics(self.metrics)
                    print_green(f"📡 Metrics create e collegate (nome: {gateway_name})")
                except Exception as e:
                    print_yellow(f"⚠️ Errore avvio metriche: {e}")
                    self.metrics = None
            
            self.reticulum.init()
            self.reticulum_initialized = True
            
            if METRICS_AVAILABLE and self.metrics:
                try:
                    self.metrics.start_query_loop(interval=3600, max_peers=10, max_hops=3)
                    print_green("📡 Metriche gateway avviate")
                except Exception as e:
                    print_yellow(f"⚠️ Errore avvio query loop: {e}")
            else:
                print_yellow("⚠️ Metrics non disponibili")
            
            status = self.reticulum.get_status()
            print_green("📡 Reticulum attivo per tutta la sessione")
            print_yellow(f"   Gateway Hash: {status.get('gateway_address', 'N/A')}")
            print_yellow(f"   Wallet Hash:  {status.get('wallet_address', 'N/A')}")
            if self.metrics:
                print_green(f"   Metrics: ✅ Disponibili")
            else:
                print_red(f"   Metrics: ❌ NON DISPONIBILI")
    
    def set_use_internet(self, enabled: bool) -> bool:
        """Imposta modalità internet e salva nel config"""
        self.use_internet = enabled
        
        # Aggiorna il config annuncio_config.json
        try:
            import json
            config_path = Path("annuncio_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                config["gateway"]["internet"] = "on" if enabled else "off"
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                print_green(f"✅ Config aggiornato: internet = {'on' if enabled else 'off'}")
            else:
                print_yellow("⚠️ File config non trovato, creazione...")
                config = {
                    "gateway": {"internet": "on" if enabled else "off"},
                    "wallet": {},
                    "sync": {},
                    "background": False
                }
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
        except Exception as e:
            print_yellow(f"⚠️ Errore salvataggio config: {e}")
            return False
        
        # Aggiorna anche metrics se esiste
        if self.metrics:
            self.metrics.set_use_internet(enabled)
        
        print_green(f"🌐 Internet: {'ON' if enabled else 'OFF'} (usa Reticulum)")
        return True

    def _update_proxy(self):
        """Imposta le variabili d'ambiente per proxy SOCKS5 se TOR è attivo."""
        if self.use_tor:
            proxy = f"socks5h://127.0.0.1:{self.tor_socks_port}"
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy
            print_blue(f"🧅 TOR attivo: proxy su {proxy}")
        else:
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            print_green("🌐 TOR disattivato, connessione diretta")
        self._client = None  # invalida il client

    def _test_tor(self) -> bool:
        """Verifica se TOR è raggiungibile (test socket veloce)."""
        if not self.use_tor:
            return False
        try:
            import socket
            # Prova su 127.0.0.1
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(('127.0.0.1', self.tor_socks_port))
            sock.close()
            return True
        except Exception:
            # Se fallisce su 127.0.0.1, prova su localhost
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect(('localhost', self.tor_socks_port))
                sock.close()
                return True
            except:
                return False

    def set_use_tor(self, enabled: bool) -> bool:
        """Attiva/disattiva TOR e salva la configurazione."""
        self.use_tor = enabled
        self._update_proxy()
        # Salva nel file di configurazione
        try:
            import json
            config_path = Path("annuncio_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                config["gateway"]["use_tor"] = "on" if enabled else "off"
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                print_green(f"🧅 Config TOR aggiornato: {'on' if enabled else 'off'}")
            return True
        except Exception as e:
            print_red(f"❌ Errore salvataggio config TOR: {e}")
            return False

    def _get_public_ip(self) -> str:
        """Ottiene l'IP pubblico (normale o via TOR)."""
        try:
            import requests
            proxies = {}
            if self.use_tor:
                proxy = f"socks5h://127.0.0.1:{self.tor_socks_port}"
                proxies = {'http': proxy, 'https': proxy}
            r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
            if r.status_code == 200:
                return r.json().get("ip", "N/A")
        except:
            pass
        return "N/A"

    # ============================================================
    # RETICULUM - RPC PER OPERAZIONI LEDGER
    # ============================================================

    def _select_best_gateway(self, asset: str = None) -> Optional[Dict]:
        """
        Seleziona il miglior gateway usando GatewayMetrics.
        asset: se specificato, cerca gateway che supporta quell'asset
        """
        if not self.metrics:
            print_red("❌ Metrics non disponibili")
            return None
        
        # 🔥 USA GatewayMetrics.get_best_gateway() che già filtra per has_internet=1
        best = self.metrics.get_best_gateway(asset)
        
        if best:
            # 🔥 SE TOR ON: verifica che il gateway abbia TOR
            if self.use_tor:
                if not (best.get('tor_enabled') and best.get('tor_reachable')):
                    # Il miglior gateway non ha TOR, cerco uno con TOR
                    peers = self.metrics.get_all_peers()
                    tor_candidates = [
                        p for p in peers 
                        if p.get('is_online') 
                        and p.get('has_internet') 
                        and p.get('tor_enabled') 
                        and p.get('tor_reachable')
                    ]
                    if not tor_candidates:
                        print_red("🧅 TOR ON: NESSUN gateway con TOR + Internet disponibile!")
                        return None
                    # Ordina come get_best_gateway
                    tor_candidates.sort(key=lambda p: (
                        p.get('hops', 999),
                        p.get('latency_ms', 99999),
                        -p.get('reputation', 0),
                        -p.get('reliability', 0)
                    ))
                    best = tor_candidates[0]
                    print_blue(f"🧅 TOR ON: usando gateway con TOR: {best.get('name', 'UNKNOWN')}")
                else:
                    print_blue(f"🧅 TOR ON: gateway con TOR: {best.get('name', 'UNKNOWN')}")
            else:
                print_green(f"🌐 Gateway scelto: {best.get('name', 'UNKNOWN')}")
            
            return best
        
        print_red("❌ Nessun gateway disponibile con Internet")
        return None

    def _send_reticulum_request(self, gateway_id: str, request: Dict, timeout: int = 60) -> Optional[Dict]:
        """Invia una richiesta RPC a un gateway e attende risposta (supporta Resource)"""
        if not self.reticulum:
            print_red("❌ Reticulum non disponibile")
            return None
        
        try:
            import json
            import threading
            import tempfile
            from RNS import Packet, Link, Identity, Destination, Resource
            
            dest_hash = bytes.fromhex(gateway_id)
            server_identity = Identity.recall(dest_hash)
            if not server_identity:
                print_red("❌ Identity del gateway non trovata")
                return None
            
            server_destination = Destination(
                server_identity,
                Destination.OUT,
                Destination.SINGLE,
                "rns", "rec", "gateway"
            )
            
            link = Link(server_destination)
            
            # 🔥 IMPOSTA LA STRATEGIA PER ACCETTARE RESOURCE
            link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
            
            # 🔥 VARIABILI PER IL RESOURCE
            resource_data = None
            resource_received = threading.Event()
            resource_error = None
            
            def on_resource_started(resource):
                print(f"📥 Ricezione resource iniziata ({resource.total_size} bytes)")
            
            def on_resource_concluded(resource):
                nonlocal resource_data, resource_error
                if resource.status == RNS.Resource.COMPLETE:
                    try:
                        resource_data = resource.data.read()
                        print(f"✅ Resource ricevuto ({len(resource_data)} bytes)")
                    except Exception as e:
                        resource_error = str(e)
                        print(f"❌ Errore lettura resource: {e}")
                else:
                    resource_error = f"Resource fallito: {resource.status}"
                    print(f"❌ {resource_error}")
                resource_received.set()
            
            link.set_resource_started_callback(on_resource_started)
            link.set_resource_concluded_callback(on_resource_concluded)
            
            link_established = threading.Event()
            
            def on_link_established(link_obj):
                link_established.set()
            
            link.set_link_established_callback(on_link_established)
            
            if not link_established.wait(10):
                link.teardown()
                print_red("❌ Timeout connessione al gateway")
                return None
            
            # 🔥 ATTESA PACCHETTI JSON O RESOURCE
            response_data = None
            response_received = threading.Event()
            
            def on_packet_received(message, packet):
                nonlocal response_data
                try:
                    data = json.loads(message.decode())
                    if data.get("type") == "ledger_relay_response":
                        response_data = data
                        response_received.set()
                    else:
                        print(f"📥 Pacchetto ricevuto: {data.get('type', 'unknown')}")
                except:
                    print("📥 Pacchetto non JSON")
            
            link.set_packet_callback(on_packet_received)
            
            # 🔥 PREPARA LA RICHIESTA
            request_json = json.dumps(request)
            request_bytes = request_json.encode()
            
            # 🔥 SE LA RICHIESTA SUPERA L'MTU, USA RESOURCE
            if len(request_bytes) > 450:
                print(f"📤 Richiesta grande ({len(request_bytes)} bytes), invio via Resource...")
                try:
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as tmp:
                        tmp.write(request_bytes)
                        tmp_path = tmp.name
                    
                    file_obj = open(tmp_path, 'rb')
                    resource = Resource(file_obj, link, is_response=False)
                    resource.data_size = len(request_bytes)
                    print(f"📤 Resource inviato ({len(request_bytes)} bytes)")
                    time.sleep(0.5)  # Dai tempo per l'invio
                except Exception as e:
                    print(f"⚠️ Errore invio Resource: {e}")
                    # Fallback: pacchetto normale
                    Packet(link, request_bytes).send()
                    print_blue(f"📤 Richiesta inviata a {gateway_id[:16]}... (pacchetto, {len(request_bytes)} bytes)")
            else:
                # 🔥 PACCHETTO PICCOLO
                Packet(link, request_bytes).send()
                print_blue(f"📤 Richiesta inviata a {gateway_id[:16]}... ({len(request_bytes)} bytes)")
            
            # 🔥 ASPETTA PACCHETTO O RESOURCE
            start_time = time.time()
            while time.time() - start_time < timeout:
                if response_received.is_set():
                    break
                if resource_received.is_set():
                    break
                time.sleep(0.1)
            
            # 🔥 SE ABBIAMO RICEVUTO UN RESOURCE
            if resource_received.is_set():
                if resource_data and not resource_error:
                    try:
                        return json.loads(resource_data.decode())
                    except Exception as e:
                        print_red(f"❌ Errore decodifica resource: {e}")
                        return None
                else:
                    print_red(f"❌ Errore resource: {resource_error}")
                    return None
            
            # 🔥 SE ABBIAMO RICEVUTO UN PACCHETTO JSON
            if response_received.is_set() and response_data:
                return response_data
            
            # 🔥 TIMEOUT
            link.teardown()
            print_red(f"⏰ Timeout attesa risposta ({timeout}s)")
            return None
            
        except Exception as e:
            print_red(f"❌ Errore richiesta Reticulum: {e}")
            return None


    def get_balance(self, refresh: bool = True) -> Dict[str, Any]:
        """Ottiene il saldo - usa internet o reticulum in base al config"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "balance": 0.0, "crypto": "XRP", "message": "No wallet"}
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # 🔥 SE INTERNET OFF, USA RETICULUM (CON CONTROLLO TOR)
        if not self.use_internet:
            # 🔥 CONTROLLO DIRETTO: SE TOR ON, VERIFICA GATEWAY TOR
            if self.use_tor and self.metrics:
                peers = self.metrics.get_all_peers()
                tor_gateways = [p for p in peers if p.get('is_online') and p.get('tor_enabled') and p.get('tor_reachable')]
                if not tor_gateways:
                    print_red("🧅 TOR ON: NESSUN gateway con TOR disponibile!")
                    print_yellow("   Le operazioni anonime non sono possibili.")
                    return {"success": False, "balance": 0.0, "crypto": "XRP", "message": "Nessun gateway TOR disponibile"}
            return self._get_balance_reticulum()
        
        # 🔥 ALTRIMENTI USA INTERNET
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            try:
                balance = manager.get_balance(refresh)
                return {"success": True, "balance": balance, "crypto": "XLM", "message": "OK"}
            except Exception as e:
                return {"success": False, "balance": 0.0, "crypto": "XLM", "message": str(e)}
        
        try:
            balance = manager.get_balance(refresh)
            return {"success": True, "balance": balance, "crypto": "XRP", "message": "OK"}
        except Exception as e:
            return {"success": False, "balance": 0.0, "crypto": "XRP", "message": str(e)}

    def get_history(self, limit: int = 10) -> Dict[str, Any]:
        """Ottiene lo storico transazioni - usa internet o reticulum in base al config"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "transactions": [], "count": 0, "message": "No wallet"}
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # 🔥 SE INTERNET OFF, USA RETICULUM (CON CONTROLLO TOR)
        if not self.use_internet:
            # 🔥 CONTROLLO DIRETTO: SE TOR ON, VERIFICA GATEWAY TOR
            if self.use_tor and self.metrics:
                peers = self.metrics.get_all_peers()
                tor_gateways = [p for p in peers if p.get('is_online') and p.get('tor_enabled') and p.get('tor_reachable')]
                if not tor_gateways:
                    print_red("🧅 TOR ON: NESSUN gateway con TOR disponibile!")
                    print_yellow("   Le operazioni anonime non sono possibili.")
                    return {"success": False, "transactions": [], "count": 0, "message": "Nessun gateway TOR disponibile"}
            return self._get_history_reticulum(limit)
        
        # 🔥 ALTRIMENTI USA INTERNET (CODICE ORIGINALE INALTERATO)
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return {"success": False, "transactions": [], "count": 0, "message": "XLM history not implemented in backend"}
        
        address = manager.get_address()
        network = manager.network
        
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
            response = client.request(request)
            
            if response.status != ResponseStatus.SUCCESS:
                return {"success": False, "transactions": [], "count": 0, "message": str(response.status)}
            
            transactions = response.result.get("transactions", [])
            
            return {
                "success": True,
                "transactions": transactions,
                "count": len(transactions),
                "address": address,
                "network": network,
                "message": "OK"
            }
        except Exception as e:
            return {"success": False, "transactions": [], "count": 0, "message": str(e)}

    def _get_balance_reticulum(self) -> Dict[str, Any]:
        """Ottiene il saldo via Reticulum da un gateway"""
        if not self.reticulum or not self.metrics:
            return {"success": False, "balance": 0, "message": "Reticulum non disponibile"}
        
        gateway = self._select_best_gateway()
        if not gateway:
            return {"success": False, "balance": 0, "message": "Nessun gateway disponibile"}
        
        address = self.wallet.get_address()
        crypto = self.wallet.get_crypto_type()
        
        request = {
            "type": "ledger_relay",
            "version": "1.0",
            "operation": "get_balance",
            "payload": {
                "address": address,
                "crypto": crypto
            },
            "timestamp": int(time.time()),
            "client_gateway_id": self.reticulum.gateway_address
        }
        
        print_blue(f"📡 Richiesta saldo via Reticulum a {gateway.get('name', 'UNKNOWN')}")
        
        response = self._send_reticulum_request(gateway['gateway_id'], request)
        
        if response and response.get("success"):
            result = response.get("result", {})
            return {
                "success": True,
                "balance": result.get("balance", 0),
                "crypto": result.get("crypto", crypto),
                "message": f"Saldo da gateway {gateway.get('name', 'UNKNOWN')}"
            }
        
        return {
            "success": False,
            "balance": 0,
            "message": response.get("error", "Errore richiesta Reticulum")
        }

    def _get_history_reticulum(self, limit: int = 10) -> Dict[str, Any]:
        """Ottiene lo storico transazioni via Reticulum da un gateway"""
        if not self.reticulum or not self.metrics:
            return {"success": False, "transactions": [], "message": "Reticulum non disponibile"}
        
        gateway = self._select_best_gateway()
        if not gateway:
            return {"success": False, "transactions": [], "message": "Nessun gateway disponibile"}
        
        address = self.wallet.get_address()
        crypto = self.wallet.get_crypto_type()
        network = self.wallet._xrp_manager.network
        
        request = {
            "type": "ledger_relay",
            "version": "1.0",
            "operation": "get_history",
            "payload": {
                "address": address,
                "crypto": crypto,
                "network": network,
                "limit": limit
            },
            "timestamp": int(time.time()),
            "client_gateway_id": self.reticulum.gateway_address
        }
        
        print_blue(f"📡 Richiesta storico via Reticulum a {gateway.get('name', 'UNKNOWN')}")
        
        response = self._send_reticulum_request(gateway['gateway_id'], request)
        
        if response and response.get("success"):
            result = response.get("result", {})
            return {
                "success": True,
                "transactions": result.get("transactions", []),
                "count": result.get("count", 0),
                "address": address,
                "network": network,
                "message": f"Storico da gateway {gateway.get('name', 'UNKNOWN')}"
            }
        
        return {
            "success": False,
            "transactions": [],
            "count": 0,
            "message": response.get("error", "Errore richiesta Reticulum")
        }

    # ============================================================
    # UTILITY
    # ============================================================
    
    def _validate_wallet_name(self, name: str) -> bool:
        if not name:
            print_red("❌ Nome wallet vuoto")
            return False
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            print_red(f"❌ Nome wallet non valido: {name}")
            print_yellow("   Usa solo lettere, numeri, underscore (_) e trattini (-)")
            return False
        return True
    
    def _get_active_wallet_name(self) -> str:
        if self.active_wallet_name_file.exists():
            return self.active_wallet_name_file.read_text().strip()
        return ""
    
    def _set_active_wallet_name(self, name: str) -> None:
        if not self._validate_wallet_name(name):
            return
        with open(self.active_wallet_name_file, "w") as f:
            f.write(name)
    
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
    
    # ============================================================
    # ENCRYPTION
    # ============================================================
    
    def _encrypt_data(self, data: Dict[str, Any]) -> str:
        from core_wrapper import encrypt_wallet
        if not self._wallet_password:
            raise ValueError("Password required for encryption")
        json_str = json.dumps(data, indent=2, default=str)
        return encrypt_wallet(json_str, self._wallet_password)
    
    def _decrypt_data(self, content: str) -> Optional[Dict[str, Any]]:
        from core_wrapper import decrypt_wallet, is_encrypted_wallet
        if not content:
            return None
        if not self._wallet_password:
            raise ValueError("Password required for decryption")
        if is_encrypted_wallet(content):
            json_str = decrypt_wallet(content, self._wallet_password)
            return json.loads(json_str)
        else:
            return json.loads(content)
    
    def _has_encrypted_files(self) -> bool:
        from core_wrapper import is_encrypted_wallet
        if os.path.exists("xrp_data.json"):
            try:
                with open("xrp_data.json", 'r') as f:
                    if is_encrypted_wallet(f.read().strip()):
                        return True
            except:
                pass
        if os.path.exists("wallet_core.db"):
            try:
                with open("wallet_core.db", 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    if content and is_encrypted_wallet(content):
                        return True
            except:
                pass
        if os.path.exists("wallet_cli.db"):
            try:
                with open("wallet_cli.db", 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    if content and is_encrypted_wallet(content):
                        return True
            except:
                pass
        if self.wallets_dir.exists():
            for f in self.wallets_dir.glob("*.json"):
                try:
                    with open(f, 'r') as fp:
                        if is_encrypted_wallet(fp.read().strip()):
                            return True
                except:
                    pass
        return False
    
    # ============================================================
    # SAVE / LOAD WALLET
    # ============================================================
    
    def _save_wallet_as(self, name: str) -> bool:
        if not self.wallet or not self.wallet._xrp_manager:
            return False
        if not self._validate_wallet_name(name):
            return False
        
        manager = self.wallet._xrp_manager
        if not manager.is_loaded():
            return False
        
        dest = self.wallets_dir / f"{name}.json"
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
        
        try:
            from core_wrapper import encrypt_wallet
            json_str = json.dumps(data, indent=2, default=str)
            encrypted = encrypt_wallet(json_str, self._wallet_password)
            with open(dest, 'w') as f:
                f.write(encrypted)
            # 🔥 NON STAMPARE NIENTE! (lo fa già wallet_manager.py)
            return True
        except Exception as e:
            print_red(f"❌ Encryption error: {e}")
            return False
    
    def _switch_wallet(self, name: str) -> bool:
        if not self._validate_wallet_name(name):
            return False
        
        source = self.wallets_dir / f"{name}.json"
        try:
            source.resolve().relative_to(self.wallets_dir.resolve())
        except ValueError:
            print_red(f"❌ Invalid path: {source}")
            return False
        
        if not source.exists():
            return False
        
        try:
            from core_wrapper import encrypt_wallet, decrypt_wallet, is_encrypted_wallet
            
            with open(source, 'r') as f:
                content = f.read().strip()
            
            if is_encrypted_wallet(content):
                if not self._wallet_password:
                    print_red("❌ Wallet encrypted but no password!")
                    return False
                json_str = decrypt_wallet(content, self._wallet_password)
                wallet_data = json.loads(json_str)
            else:
                with open(source, 'r') as f:
                    data = json.load(f)
                encrypted = encrypt_wallet(json.dumps(data, indent=2, default=str), self._wallet_password)
                with open(source, 'w') as f:
                    f.write(encrypted)
                wallet_data = data
            
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
                    info = WalletInfo.from_dict(w_data)
                    manager._derived_wallets[f"{info.keyword}:{info.index}"] = info
                except:
                    pass
            
            if self.wallet and self.wallet._xrp_manager:
                self.wallet._xrp_manager.network = saved_network
                self.wallet._xrp_manager.crypto_type = saved_crypto
                self.wallet._xrp_manager.save()
            
            self._invalidate_cache()
            
            self._set_active_wallet_name(name)
            
            print_green(f"✅ Switched to wallet: {name}")
            print_yellow(f"🌐 Network: {saved_network.upper()}")
            print_yellow(f"🪙 Crypto: {saved_crypto}")
            return True
        except Exception as e:
            print_red(f"❌ Error switching wallet: {e}")
            return False
    
    def _invalidate_cache(self):
        """Invalida la cache quando i dati cambiano"""
        self._cached_wallet_list = None
        self._cached_wallet_list_time = 0
    
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
    # GET WALLET LIST - CON CACHE
    # ============================================================
    
    def _get_wallet_list(self) -> List[Dict]:
        if self._cached_wallet_list is not None:
            return self._cached_wallet_list
        
        wallets = []
        for file in self.wallets_dir.glob("*.json"):
            try:
                with open(file) as f:
                    content = f.read().strip()
                data = self._decrypt_data(content)
                if data is None:
                    continue
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
                    "is_active": file.stem == self._get_active_wallet_name()
                })
            except Exception as e:
                pass
        
        self._cached_wallet_list = wallets
        return wallets
    
    # ============================================================
    # INIT - COMPLETO
    # ============================================================
    
    def init(self, network: str = None):
        """Inizializza il wallet"""
        active = self._get_active_wallet_name()
        
        # Default
        final_network = "testnet"
        final_crypto = "XRP"
        
        if active:
            if not self._validate_wallet_name(active):
                print_red(f"⚠️ Nome wallet attivo non valido: {active}")
                active = None
        
        if active:
            wallet_file = self.wallets_dir / f"{active}.json"
            try:
                wallet_file.resolve().relative_to(self.wallets_dir.resolve())
            except ValueError:
                print_red(f"❌ Percorso non valido: {wallet_file}")
                active = None
            
            if active and wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        content = f.read().strip()
                    
                    # 🔥 DECIFRA IL FILE
                    data = self._decrypt_data(content)
                    if data:
                        final_network = data.get("network", "testnet")
                        final_crypto = data.get("crypto_type", "XRP")
                    else:
                        print_yellow(f"⚠️ Impossibile decifrare {active}, uso valori di default")
                        final_network = "testnet"
                        final_crypto = "XRP"
                except Exception as e:
                    print_yellow(f"⚠️ Errore lettura wallet: {e}")
                    final_network = "testnet"
                    final_crypto = "XRP"
            else:
                final_network = "testnet"
                final_crypto = "XRP"
        else:
            final_network = network if network else "testnet"
            final_crypto = "XRP"
        
        # 🔥 CREA IL WALLET PASSANDO LA PASSWORD
        self.wallet = create_wallet(
            self.data_file,
            crypto=final_crypto,
            network=final_network,
            password=self._wallet_password
        )
        
        # 🔥 CARICA IL WALLET ATTIVO NEL MANAGER (dopo che è stato inizializzato)
        if active and self.wallet and self.wallet._xrp_manager:
            manager = self.wallet._xrp_manager
            wallet_file = self.wallets_dir / f"{active}.json"
            if wallet_file.exists():
                try:
                    with open(wallet_file) as f:
                        content = f.read().strip()
                    data = self._decrypt_data(content)
                    if data:
                        manager.seed_type = data.get("seed_type")
                        manager.seed_phrase = data.get("seed_phrase")
                        manager.seed_numbers = data.get("seed_numbers")
                        manager.passphrase = data.get("passphrase", "")
                        manager.base_seed_xrp = data.get("base_seed_xrp")
                        manager.base_seed_stellar = data.get("base_seed_stellar")
                        manager._correct_address = data.get("current_address")
                        manager.crypto_type = data.get("crypto_type", final_crypto)
                        manager.network = data.get("network", final_network)
                        
                        base_private_hex = data.get("base_private")
                        if base_private_hex:
                            manager.base_private = bytes.fromhex(base_private_hex)
                        
                        manager._derived_wallets = {}
                        for w_data in data.get("derived_wallets", []):
                            try:
                                info = WalletInfo.from_dict(w_data)
                                manager._derived_wallets[f"{info.keyword}:{info.index}"] = info
                            except:
                                pass
                        
                        print_green(f"✅ Wallet '{active}' caricato")
                    else:
                        print_yellow(f"⚠️ Wallet '{active}' non caricato (decifratura fallita)")
                except Exception as e:
                    print_yellow(f"⚠️ Errore caricamento wallet '{active}': {e}")
        
        # 🔥 PRENDI IL CORE DAL MANAGER
        if self.wallet and self.wallet._xrp_manager and hasattr(self.wallet._xrp_manager, 'core'):
            self.wallet.core = self.wallet._xrp_manager.core
        
        # 🔥 USA IL NETWORK FINALE
        final_network = self.wallet._xrp_manager.network if self.wallet and self.wallet._xrp_manager else final_network
        final_crypto = self.wallet._xrp_manager.crypto_type if self.wallet and self.wallet._xrp_manager else final_crypto
        
        print_green(f"✅ Wallet: {active or 'nuovo'} | Rete: {final_network.upper()} | Crypto: {final_crypto}")
        return self.wallet
    
    # ============================================================
    # WALLET MANAGEMENT - PUBBLICHE
    # ============================================================
    
    def create_wallet(self, name: str = "default", crypto: str = "XRP", network: str = "testnet", 
                      strength: int = 256, passphrase: str = "") -> Dict[str, Any]:
        """Crea un nuovo wallet con strength e passphrase opzionali"""
        if not self.wallet:
            self.init(network)
        if not self._validate_wallet_name(name):
            return {"success": False, "error": "Invalid wallet name"}
        
        crypto = crypto.upper()
        if crypto not in ["XRP", "XLM"]:
            return {"success": False, "error": f"Crypto non supportata: {crypto}"}
        
        network = network.lower()
        if network not in ["testnet", "mainnet", "devnet"]:
            return {"success": False, "error": f"Rete non supportata: {network}"}
        
        manager = self.wallet._xrp_manager
        if network != manager.network:
            manager.set_network(network)
        
        result = self.wallet.create_wallet(name, crypto, strength=strength, passphrase=passphrase)
        
        # 🔥 SALVA SOLO UNA VOLTA!
        self.wallet.save()
        self._save_wallet_as(name)
        self._set_active_wallet_name(name)
        self._invalidate_cache()
        
        return {
            "success": True,
            "identity_id": result.get("identity_id", ""),
            "address": result.get("address", ""),
            "mnemonic": result.get("mnemonic", ""),
            "word_count": result.get("word_count", 0),
            "seed": result.get("seed", ""),
            "message": f"Wallet '{name}' created"
        }
    
    def import_wallet(self, seed_input: str, name: str = "imported", crypto: str = "auto", 
                      network: str = "testnet", passphrase: str = "") -> Dict[str, Any]:
        """Importa un wallet con supporto per passphrase"""
        if not self.wallet:
            self.init(network)
        if not self._validate_wallet_name(name):
            return {"success": False, "error": "Invalid wallet name"}
        
        network = network.lower()
        if network not in ["testnet", "mainnet", "devnet"]:
            return {"success": False, "error": f"Rete non supportata: {network}"}
        
        try:
            manager = self.wallet._xrp_manager
            if network != manager.network:
                manager.set_network(network)
            
            cleaned = seed_input
            cleaned = re.sub(r'[A-Ha-h]:', '', cleaned)
            cleaned = re.sub(r',', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            numbers_parts = cleaned.split()
            
            import_type = manager.detect_input_type(seed_input)
            crypto_param = None
            if crypto and crypto.lower() != "auto":
                crypto_param = crypto.upper()
                if crypto_param not in ["XRP", "XLM"]:
                    return {"success": False, "error": f"Crypto non supportata: {crypto_param}"}
            
            # USA LA PASSPHRASE PASSATA
            if len(numbers_parts) == 8 and all(p.isdigit() and len(p) == 6 for p in numbers_parts):
                result = self.wallet.import_wallet(" ".join(numbers_parts), name, crypto_param)
            else:
                result = self.wallet.import_wallet(seed_input, name, crypto_param, passphrase=passphrase)
            
            # 🔥 SALVA SOLO UNA VOLTA! (xrp_data.json + wallets/{name}.json)
            # self.wallet.save() SALVA GIÀ xrp_data.json
            self.wallet.save()
            
            # 🔥 SALVA IN wallets/{name}.json (COPIA DI BACKUP)
            self._save_wallet_as(name)
            
            # 🔥 SETTA COME ATTIVO
            self._set_active_wallet_name(name)
            self._invalidate_cache()
            
            return {
                "success": True,
                "identity_id": result.get("identity_id", ""),
                "address": result.get("address", ""),
                "seed_type": result.get("seed_type", ""),
                "message": f"Wallet '{name}' imported"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def switch_wallet(self, name: str) -> Dict[str, Any]:
        if self._switch_wallet(name):
            self._invalidate_cache()
            # 🔥 Restituisci anche network e crypto
            active = self.get_active_wallet()
            return {
                "success": True, 
                "message": f"Switched to '{name}'",
                "network": active.get("network", "testnet"),
                "crypto": active.get("crypto", "XRP")
            }
        return {"success": False, "message": f"Wallet '{name}' not found"}
    
    def get_active_wallet(self) -> Dict[str, Any]:
        name = self._get_active_wallet_name()
        manager = self.wallet._xrp_manager if self.wallet else None
        if manager and manager.is_loaded():
            return {
                "name": name,
                "address": manager.get_address(),
                "crypto": manager.crypto_type,
                "network": manager.network,
                "loaded": True
            }
        return {"name": name, "address": "", "crypto": "XRP", "network": "testnet", "loaded": False}
    
    def list_wallets(self) -> List[Dict[str, Any]]:
        return self._get_wallet_list()
    
    def remove_wallet(self, name: str) -> Dict[str, Any]:
        active = self._get_active_wallet_name()
        if name == active:
            return {"success": False, "message": "Cannot remove active wallet"}
        wallet_file = self.wallets_dir / f"{name}.json"
        if wallet_file.exists():
            wallet_file.unlink()
            self._invalidate_cache()
            return {"success": True, "message": f"Wallet '{name}' removed"}
        return {"success": False, "message": f"Wallet '{name}' not found"}
    
    # ============================================================
    # WALLET MANAGEMENT - PUBBLICHE
    # ============================================================

    def get_wallet_info(self) -> Dict[str, Any]:
        """Info del wallet attivo (senza parametri)."""
        manager = self.wallet._xrp_manager if self.wallet else None
        if not manager or not manager.is_loaded():
            return {"success": False, "message": "No wallet loaded"}
        info = manager.get_seed_info()
        return {
            "success": True,
            "crypto": manager.crypto_type,
            "network": manager.network,
            "address": manager.get_address(),
            "seed_type": manager.seed_type,
            "balance": info.get("balance", 0.0),
            "mnemonic": info.get("seed_phrase"),
            "secret_numbers": info.get("formatted"),
            "xrp_seed": info.get("seed_xrp"),
            "stellar_seed": info.get("seed_stellar"),
            "private_key": info.get("private_key"),
            "derived_wallets": [w.to_dict() for w in manager._derived_wallets.values()],
            "message": "OK"
        }

    def derive_addresses(self, keyword: str = "default", count: int = 5) -> Dict[str, Any]:
        """Deriva count indirizzi usando il manager."""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "addresses": [], "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        crypto_type = manager.crypto_type
        
        if crypto_type == "XLM":
            try:
                address = manager.get_address()
                addresses = [{"address": address, "index": 0, "keyword": keyword}]
                return {"success": True, "addresses": addresses, "message": "OK"}
            except Exception as e:
                return {"success": False, "addresses": [], "message": str(e)}
        
        try:
            # 🔥 CHIAMA IL MANAGER CHE DERIVA CORRETTAMENTE
            wallet_infos = manager.derive_addresses(keyword, count)
            addresses = []
            for info in wallet_infos:
                addresses.append({
                    "keyword": info.keyword,
                    "index": info.index,
                    "address": info.address,
                    "private_key": info.private_key,
                    "public_key": info.public_key,
                    "seed_xrp": info.seed_xrp
                })
            return {"success": True, "addresses": addresses, "message": "OK"}
        except Exception as e:
            return {"success": False, "addresses": [], "message": str(e)}
    
    def get_address(self) -> Dict[str, Any]:
        address = self.wallet.get_address() if self.wallet else None
        if address:
            return {"success": True, "address": address, "message": "OK"}
        return {"success": False, "address": "", "message": "No address"}
    
    
    def export_wallet(self, include_private: bool = False) -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "data": {}, "message": "No wallet"}
        data = self.wallet._xrp_manager.export_wallet("dict", include_private)
        return {"success": True, "data": data, "message": "OK"}
    
    # ============================================================
    # BALANCE
    # ============================================================
    
    def get_balance(self, refresh: bool = True) -> Dict[str, Any]:
        """Ottiene il saldo - usa internet o reticulum in base al config"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "balance": 0.0, "crypto": "XRP", "message": "No wallet"}
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # 🔥 SE INTERNET OFF, USA RETICULUM
        if not self.use_internet:
            return self._get_balance_reticulum()
        
        # 🔥 ALTRIMENTI USA INTERNET
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            try:
                balance = manager.get_balance(refresh)
                return {"success": True, "balance": balance, "crypto": "XLM", "message": "OK"}
            except Exception as e:
                return {"success": False, "balance": 0.0, "crypto": "XLM", "message": str(e)}
        
        try:
            balance = manager.get_balance(refresh)
            return {"success": True, "balance": balance, "crypto": "XRP", "message": "OK"}
        except Exception as e:
            return {"success": False, "balance": 0.0, "crypto": "XRP", "message": str(e)}

    
    # ============================================================
    # TRANSACTIONS
    # ============================================================
    
    def send_payment(self, to_address: str, amount: float, memo: str = "") -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "tx_hash": "", "message": "No wallet"}
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return self._send_xlm(to_address, amount, memo)
        
        if not self.use_internet:
            # 🔥 CONTROLLO DIRETTO: SE TOR ON, VERIFICA GATEWAY TOR
            if self.use_tor and self.metrics:
                peers = self.metrics.get_all_peers()
                tor_gateways = [p for p in peers if p.get('is_online') and p.get('tor_enabled') and p.get('tor_reachable')]
                if not tor_gateways:
                    print_red("🧅 TOR ON: NESSUN gateway con TOR disponibile!")
                    return {"success": False, "tx_hash": "", "message": "Nessun gateway TOR disponibile"}
            result = self._send_payment_reticulum(to_address, amount, memo)
            result["via_reticulum"] = True
            return result
        
        return self._send_xrp(to_address, amount, memo)
    
    def _send_xlm(self, to_address: str, amount: float, memo: str) -> Dict[str, Any]:
        args = [to_address, str(amount)]
        if memo:
            args.append(memo)
        send_xlm(self, args)
        return {"success": True, "tx_hash": "sent", "message": "XLM sent"}
    
    def _send_xrp(self, to_address: str, amount: float, memo: str) -> Dict[str, Any]:
        """
        Invia pagamento XRP - ADATTIVO PER TIPO DI WALLET
        """
        from xrpl.account import get_balance
        from xrpl.models.transactions import Payment
        from xrpl.transaction import autofill, sign, submit_and_wait
        from xrpl.clients import JsonRpcClient
        from xrpl.models.transactions import Memo
        from xrpl.wallet import Wallet as XRPWallet
        from xrpl.constants import CryptoAlgorithm

        manager = self.wallet._xrp_manager
        seed_type = manager.seed_type

        # 🔥 1. OTTIENI IL WALLET IN BASE AL TIPO
        try:
            if seed_type in ["bip39", "private_key"]:
                # 🔥 USA LA PRIVATE KEY DIRETTAMENTE (SECP256K1)
                private_key_hex = manager.base_private.hex() if manager.base_private else None
                if not private_key_hex:
                    return {"success": False, "tx_hash": "", "message": "Nessuna private key disponibile"}

                public_key_hex, address = manager._private_key_to_keypair(private_key_hex)
                wallet = XRPWallet(
                    public_key=public_key_hex,
                    private_key=private_key_hex,
                    algorithm=CryptoAlgorithm.SECP256K1
                )
                print_green(f"✅ Wallet SECP256K1 (da {'mnemonic' if seed_type == 'bip39' else 'private key'}): {wallet.classic_address}")

            else:
                # 🔥 PER NUMBERS, XRP_SEED, STELLAR_SEED USA IL SEED
                wallet = manager.get_wallet()
                print_green(f"✅ Wallet caricato da seed: {wallet.classic_address}")

            # 2. CONNESSIONE AL NETWORK
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/",
                "devnet": "https://s.devnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(manager.network, urls["testnet"]))
            source_address = wallet.classic_address

            # 3. VERIFICA SALDO
            balance_drops = get_balance(source_address, client)
            balance_xrp = int(balance_drops) / 1_000_000 if isinstance(balance_drops, str) else balance_drops / 1_000_000

            if balance_xrp < amount:
                return {"success": False, "tx_hash": "", "message": f"Saldo insufficiente: {balance_xrp:.6f} XRP"}

            # 4. PREPARA TRANSAZIONE
            amount_drops = str(int(amount * 1_000_000))
            payment_params = {
                "account": source_address,
                "amount": amount_drops,
                "destination": to_address
            }
            if memo:
                memo_hex = memo.encode('utf-8').hex()
                if len(memo_hex) % 2 != 0:
                    memo_hex = '0' + memo_hex
                payment_params["memos"] = [Memo(memo_data=memo_hex)]

            # 5. FIRMA E INVIO
            payment = Payment(**payment_params)
            tx = autofill(payment, client)
            signed_tx = sign(tx, wallet)
            response = submit_and_wait(signed_tx, client)

            tx_hash = response.result.get("hash", "unknown")
            result_code = response.result.get('meta', {}).get('TransactionResult')

            if result_code == "tesSUCCESS":
                return {"success": True, "tx_hash": tx_hash, "message": "Pagamento inviato con successo!"}
            else:
                return {"success": False, "tx_hash": tx_hash, "message": f"Transazione fallita: {result_code}"}

        except Exception as e:
            return {"success": False, "tx_hash": "", "message": str(e)}

    def get_history(self, limit: int = 10) -> Dict[str, Any]:
        """Ottiene lo storico transazioni - usa internet o reticulum in base al config"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "transactions": [], "count": 0, "message": "No wallet"}
        
        self._ensure_correct_network()
        manager = self.wallet._xrp_manager
        
        # 🔥 SE INTERNET OFF, USA RETICULUM (FALLBACK AGGIUNTO)
        if not self.use_internet:
            return self._get_history_reticulum(limit)
        
        # 🔥 ALTRIMENTI USA INTERNET (CODICE ORIGINALE INALTERATO)
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            return {"success": False, "transactions": [], "count": 0, "message": "XLM history not implemented in backend"}
        
        address = manager.get_address()
        network = manager.network
        
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
            response = client.request(request)
            
            if response.status != ResponseStatus.SUCCESS:
                return {"success": False, "transactions": [], "count": 0, "message": str(response.status)}
            
            transactions = response.result.get("transactions", [])
            
            return {
                "success": True,
                "transactions": transactions,
                "count": len(transactions),
                "address": address,
                "network": network,
                "message": "OK"
            }
        except Exception as e:
            return {"success": False, "transactions": [], "count": 0, "message": str(e)}
    
    def _send_payment_reticulum(self, to_address: str, amount: float, memo: str) -> Dict[str, Any]:
        if not self.reticulum or not self.metrics:
            return {"success": False, "tx_hash": "", "message": "Reticulum non disponibile"}

        gateway = self._select_best_gateway()
        if not gateway:
            return {"success": False, "tx_hash": "", "message": "Nessun gateway disponibile"}

        manager = self.wallet._xrp_manager
        seed_type = manager.seed_type

        # 1. Ottieni il wallet
        try:
            if seed_type in ["bip39", "private_key"]:
                private_key_hex = manager.base_private.hex() if manager.base_private else None
                if not private_key_hex:
                    return {"success": False, "tx_hash": "", "message": "Nessuna private key disponibile"}
                public_key_hex, address = manager._private_key_to_keypair(private_key_hex)
                from xrpl.wallet import Wallet as XRPWallet
                from xrpl.constants import CryptoAlgorithm
                wallet = XRPWallet(
                    public_key=public_key_hex,
                    private_key=private_key_hex,
                    algorithm=CryptoAlgorithm.SECP256K1
                )
            else:
                wallet = manager.get_wallet()
        except Exception as e:
            return {"success": False, "tx_hash": "", "message": f"Errore wallet: {e}"}

        # 2. Ottieni ledger corrente e sequenza dal gateway
        account_info = self._get_account_info_from_gateway(gateway, wallet.classic_address, manager.network)
        if not account_info.get("success"):
            return {"success": False, "tx_hash": "", "message": account_info.get("message", "Errore account")}
        
        sequence = account_info.get("sequence", 0)
        current_ledger = account_info.get("ledger_index", 0)
        
        if sequence == 0:
            return {"success": False, "tx_hash": "", "message": "Sequence non valida"}

        # 3. Tentativi con margine crescente
        max_attempts = 5
        margin_start = 20
        margin_increment = 10

        for attempt in range(max_attempts):
            margin = margin_start + (attempt * margin_increment)
            last_ledger = current_ledger + margin
            
            print_blue(f"📡 Tentativo {attempt+1}/{max_attempts} - Margine: {margin} ledger (LastLedger: {last_ledger})")

            # 4. Prepara e firma la transazione (con Sequence!)
            try:
                from xrpl.models.transactions import Payment
                from xrpl.transaction import sign
                from xrpl.models.transactions import Memo

                amount_drops = str(int(amount * 1_000_000))
                payment_params = {
                    "account": wallet.classic_address,
                    "amount": amount_drops,
                    "destination": to_address,
                    "sequence": sequence,
                    "last_ledger_sequence": last_ledger,
                    "fee": "10"   # <-- Fee fissa di 10 drops (0.00001 XRP)
                }
                if memo:
                    memo_hex = memo.encode('utf-8').hex()
                    if len(memo_hex) % 2 != 0:
                        memo_hex = '0' + memo_hex
                    payment_params["memos"] = [Memo(memo_data=memo_hex)]

                payment = Payment(**payment_params)
                signed_tx = sign(payment, wallet)
                signed_tx_blob = signed_tx.blob()  # stringa hex

            except Exception as e:
                print_yellow(f"⚠️ Errore preparazione tentativo {attempt+1}: {e}")
                continue

            # 5. Invia al gateway
            request = {
                "type": "ledger_relay",
                "version": "1.0",
                "operation": "submit_transaction",
                "payload": {
                    "tx_blob": signed_tx_blob,
                    "network": manager.network
                },
                "timestamp": int(time.time()),
                "client_gateway_id": self.reticulum.gateway_address
            }

            print_blue(f"📡 Invio tentativo {attempt+1} a {gateway.get('name', 'UNKNOWN')}")

            response = self._send_reticulum_request(gateway['gateway_id'], request, timeout=60)

            if response and response.get("success"):
                result = response.get("result", {})
                tx_hash = result.get("hash", "unknown")
                result_code = result.get("result_code", "unknown")

                if result_code == "tesSUCCESS":
                    return {
                        "success": True,
                        "tx_hash": tx_hash,
                        "message": f"Transazione inviata via Reticulum (tentativo {attempt+1})! Hash: {tx_hash}"
                    }
                else:
                    if result_code == "tefMAX_LEDGER":
                        print_yellow(f"⚠️ LastLedger scaduto (tentativo {attempt+1}), aumento margine...")
                        continue
                    elif result_code == "tecFAILED_SEQUENCE":
                        print_yellow(f"⚠️ Sequence scaduta (tentativo {attempt+1}), aggiorno sequence...")
                        # Richiedi nuova sequenza
                        new_info = self._get_account_info_from_gateway(gateway, wallet.classic_address, manager.network)
                        if new_info.get("success"):
                            sequence = new_info.get("sequence", sequence)
                        continue
                    else:
                        return {
                            "success": False,
                            "tx_hash": tx_hash,
                            "message": f"Transazione fallita: {result_code}"
                        }
            else:
                error = response.get("error", "Errore sconosciuto") if response else "Nessuna risposta"
                print_yellow(f"⚠️ Errore Reticulum tentativo {attempt+1}: {error}")
                continue

        return {
            "success": False,
            "tx_hash": "",
            "message": f"Transazione fallita dopo {max_attempts} tentativi."
        }


    def _get_account_info_from_gateway(self, gateway: Dict, address: str, network: str) -> Dict[str, Any]:
        """Richiede info account (sequence, balance) al gateway via Reticulum."""
        request = {
            "type": "ledger_relay",
            "version": "1.0",
            "operation": "get_account_info",
            "payload": {
                "address": address,
                "network": network
            },
            "timestamp": int(time.time()),
            "client_gateway_id": self.reticulum.gateway_address
        }
        
        response = self._send_reticulum_request(gateway['gateway_id'], request, timeout=60)
        
        if response and response.get("success"):
            result = response.get("result", {})
            return {
                "success": True,
                "sequence": result.get("sequence", 0),
                "balance": result.get("balance", 0),
                "ledger_index": result.get("ledger_index", 0)
            }
        else:
            error = response.get("error", "Nessuna risposta") if response else "Nessuna risposta"
            return {"success": False, "message": f"Errore account: {error}"}


    def _get_ledger_from_gateway(self, gateway: Dict, network: str) -> Dict[str, Any]:
        """Richiede il ledger corrente al gateway via Reticulum."""
        request = {
            "type": "ledger_relay",
            "version": "1.0",
            "operation": "get_ledger_info",
            "payload": {"network": network},
            "timestamp": int(time.time()),
            "client_gateway_id": self.reticulum.gateway_address
        }
        
        response = self._send_reticulum_request(gateway['gateway_id'], request, timeout=60)
        
        if response and response.get("success"):
            result = response.get("result", {})
            return {
                "success": True,
                "ledger_index": result.get("ledger_index", 0),
                "base_fee": result.get("base_fee", "10")
            }
        else:
            error = response.get("error", "Nessuna risposta") if response else "Nessuna risposta"
            return {"success": False, "message": f"Errore ledger: {error}"}

    def fund_testnet(self) -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        if manager.crypto_type == "XLM" and XLM_AVAILABLE:
            faucet_xlm(self)
            return {"success": True, "message": "Testnet funded"}
        return {"success": False, "message": "XRP faucet not available"}
    
    # ============================================================
    # TRUSTLINE
    # ============================================================
    
    def get_trustlines(self, refresh: bool = True) -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "trustlines": [], "count": 0, "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        trustlines = manager.get_trustlines(refresh)
        return {"success": True, "trustlines": trustlines, "count": len(trustlines), "message": "OK"}
    
    def create_trustline(self, asset: str, issuer: str, limit: float = 0) -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        result = manager.set_trustline(asset, issuer, limit)
        return result
    
    def remove_trustline(self, asset: str, issuer: str) -> Dict[str, Any]:
        """Rimuovi trustline - USA FLAG 0x00020000 per forzare la rimozione"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        # 🔥 USA limit=0 CON FLAG CORRETTO (fatto in _set_xrp_trustline)
        return manager.set_trustline(asset, issuer, 0)
    
    def get_trustline_info(self, asset: str, issuer: str = None) -> Dict[str, Any]:
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        return manager.get_trustline_balance(asset, issuer)
    
    # ============================================================
    # TOKENS
    # ============================================================
    
    def send_token(self, to_address: str, token: str, amount: float, issuer: str = None, destination_tag: int = None) -> Dict[str, Any]:
        """Invia token con supporto destination_tag"""
        if not self.wallet or not self.wallet._xrp_manager:
            return {"success": False, "tx_hash": "", "message": "No wallet"}
        
        manager = self.wallet._xrp_manager
        if not issuer:
            issuer = manager.get_address()
        
        try:
            from xrpl.models.transactions import Payment
            from xrpl.transaction import autofill_and_sign, submit_and_wait
            from xrpl.clients import JsonRpcClient
            from xrpl.models.amounts import IssuedCurrencyAmount
            
            urls = {"mainnet": "https://s1.ripple.com:51234/", "testnet": "https://s.altnet.rippletest.net:51234/", "devnet": "https://s.devnet.rippletest.net:51234/"}
            client = JsonRpcClient(urls.get(manager.network, urls["testnet"]))
            wallet = manager.get_wallet("default", 0)
            
            if len(token) == 3:
                currency = token
            else:
                currency_hex = token.encode('utf-8').hex().upper()
                currency = currency_hex.ljust(40, '0')
            
            amount_obj = IssuedCurrencyAmount(currency=currency, issuer=issuer, value=str(amount))
            
            # 🔥 COSTRUISCI PAYMENT CON DESTINATION TAG
            payment_params = {
                "account": wallet.classic_address,
                "destination": to_address,
                "amount": amount_obj
            }
            
            # 🔥 AGGIUNGI DESTINATION TAG SE FORNITO
            if destination_tag is not None:
                payment_params["destination_tag"] = destination_tag
                print(f"   Destination Tag: {destination_tag}")
            
            payment = Payment(**payment_params)
            signed_tx = autofill_and_sign(payment, client, wallet)
            response = submit_and_wait(signed_tx, client)
            tx_hash = response.result.get("hash", "unknown")
            
            return {"success": True, "tx_hash": tx_hash, "message": f"{amount} {token} sent"}
        except Exception as e:
            return {"success": False, "tx_hash": "", "message": str(e)}
    
    def receive_token_info(self, token: str, issuer: str, limit: float = 1000000.0) -> Dict[str, Any]:
        return {
            "success": True,
            "token": token,
            "issuer": issuer,
            "limit": limit,
            "message": f"Ready to receive {token}"
        }
    
    # ============================================================
    # RETICULUM - PUBBLICHE
    # ============================================================
    
    def get_ip_status(self) -> Dict[str, Any]:
        """Restituisce IP e stato per il menu."""
        if not self.use_internet:
            return {
                "ip": "N/A (Reticulum)",
                "use_tor": self.use_tor,
                "use_internet": self.use_internet
            }
        return {
            "ip": self._get_public_ip(),
            "use_tor": self.use_tor,
            "use_internet": self.use_internet
        }

    def get_gateway_status(self) -> Dict[str, Any]:
        """Ottiene lo stato del gateway con nome dal config"""
        if not self.reticulum:
            return {"success": False, "message": "Reticulum not available"}
        
        status = self.reticulum.get_status()
        
        # 🔥 LEGGI IL NOME DAL CONFIG
        gateway_name = "UNKNOWN"
        try:
            config_path = Path("annuncio_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    gateway_name = config.get("gateway", {}).get("name", "UNKNOWN")
        except:
            pass
        
        # 🔥 IP VISIBILE SOLO SE INTERNET È ON
        if self.use_internet:
            status["public_ip"] = self._get_public_ip()
        else:
            status["public_ip"] = "N/A (Reticulum)"
        
        status["use_tor"] = self.use_tor
        status["internet_on"] = self.use_internet
        status["name"] = gateway_name
        
        return {"success": True, "status": status, "message": "OK"}

    def start_gateway(self) -> Dict[str, Any]:
        if not self.reticulum:
            return {"success": False, "message": "Reticulum not available"}
        self._reticulum_gateway_start()
        return {"success": True, "message": "Gateway started"}
    
    def stop_gateway(self) -> Dict[str, Any]:
        if not self.reticulum:
            return {"success": False, "message": "Reticulum not available"}
        self.reticulum.stop_gateway()
        return {"success": True, "message": "Gateway stopped"}
    
    def _reticulum_gateway_start(self):
        if not self.reticulum:
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
    
    def discover_gateways(self, active_only: bool = False) -> Dict[str, Any]:
        """Scopri gateway - TUTTI se active_only=False, solo attivi se True"""
        if not self.reticulum:
            return {"success": False, "gateways": [], "count": 0, "message": "Reticulum not available"}
        
        gateways = self.reticulum.discover_gateways()
        
        # 🔥 SE active_only=True, APPLICA FILTRO discover_since_seconds
        if active_only:
            since = time.time() - self.reticulum_config.gateway.discover_since_seconds
            gateways = [g for g in gateways if g.get('last_seen', 0) > since]
        
        # 🔥 ORDINA PER LAST_SEEN (più recenti prima)
        gateways.sort(key=lambda x: x.get('last_seen', 0), reverse=True)
        
        return {"success": True, "gateways": gateways, "count": len(gateways), "message": "OK"}

    def discover_wallets(self, active_only: bool = False) -> Dict[str, Any]:
        """Scopri wallet - TUTTI se active_only=False, solo attivi se True"""
        if not self.reticulum:
            return {"success": False, "wallets": [], "count": 0, "message": "Reticulum not available"}
        
        wallets = self.reticulum.discover_wallets()
        
        if active_only:
            since = time.time() - self.reticulum_config.wallet.discover_since_seconds
            wallets = [w for w in wallets if w.get('last_seen', 0) > since]
        
        wallets.sort(key=lambda x: x.get('last_seen', 0), reverse=True)
        
        return {"success": True, "wallets": wallets, "count": len(wallets), "message": "OK"}
    
    def get_peer_metrics(self) -> Dict[str, Any]:
        """Ottiene le metriche dei peer - USA GatewayMetrics"""
        if not self.metrics:
            return {"success": False, "peers": [], "count": 0, "message": "Metrics not available", "stats": {}}
        
        # 🔥 PRENDE I PEER DA gateway_peers.db
        peers = self.metrics.get_all_peers()
        
        if not peers:
            return {"success": True, "peers": [], "count": 0, "message": "No peers in DB", "stats": {}}
        
        # 🔥 FILTRA: solo online con Internet (TOR gestito dopo)
        filtered = [p for p in peers if p.get('is_online') and p.get('has_internet')]
        
        # 🔥 SE TOR ON, filtra solo TOR
        if self.use_tor:
            filtered = [p for p in filtered if p.get('tor_enabled') and p.get('tor_reachable')]
            if not filtered:
                return {
                    "success": True, 
                    "peers": [], 
                    "count": 0, 
                    "message": "Nessun peer TOR + Internet disponibile", 
                    "stats": {}
                }
        
        if not filtered:
            return {
                "success": True, 
                "peers": [], 
                "count": 0, 
                "message": "Nessun peer con Internet disponibile", 
                "stats": {}
            }
        
        # 🔥 ORDINA COME get_best_gateway()
        filtered.sort(key=lambda p: (
            p.get('hops', 999),
            p.get('latency_ms', 99999),
            -p.get('reputation', 0),
            -p.get('reliability', 0)
        ))
        
        # 🔥 CALCOLA STATS
        stats = {
            "total_peers": len(filtered),
            "online_peers": len(filtered),
            "offline_peers": 0,
            "avg_reputation": sum(p.get('reputation', 0) for p in filtered) / len(filtered) if filtered else 0,
            "avg_latency_ms": sum(p.get('latency_ms', 0) for p in filtered if p.get('latency_ms')) / len(filtered) if filtered else 0,
            "tor_peers": sum(1 for p in filtered if p.get('tor_enabled') and p.get('tor_reachable')),
            "xrp_peers": sum(1 for p in filtered if p.get('xrp_reachable')),
            "stellar_peers": sum(1 for p in filtered if p.get('stellar_reachable')),
            "internet_peers": len(filtered),
        }
        
        return {
            "success": True,
            "peers": filtered,
            "count": len(filtered),
            "message": "OK",
            "stats": stats
        }

    def get_best_gateway(self, asset: str) -> Dict[str, Any]:
        if not self.metrics:
            return {"success": False, "message": "Metrics not available"}
        best = self.metrics.get_best_gateway(asset)
        return {"success": True, "gateway": best, "message": "OK"} if best else {"success": False, "message": "No gateway found"}

    def _show_single_peer(self, peer: Dict):
        """Mostra un singolo peer in formato tabella - COMPLETO (con TOR)"""
        print_bold(f"\n🔍 PEER: {peer.get('name', 'UNKNOWN')}")
        print("=" * 120)
        print(f"{'ID':<38} {'Hops':<6} {'RTT':<10} {'XRP':<14} {'Stellar':<14} {'Rep':<5} {'Internet':<9} {'TOR':<6} {'Ultimo visto':<15}")
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
        
        # 🔥 STATO TOR
        tor_enabled = peer.get('tor_enabled', False)
        tor_reachable = peer.get('tor_reachable', False)
        if tor_enabled and tor_reachable:
            tor_str = "🧅✅"
        elif tor_enabled:
            tor_str = "🧅❌"
        else:
            tor_str = "—"
        
        last_seen = peer.get('last_seen')
        last_seen_str = format_time_ago(last_seen)
        
        print(f"{gid:<38} {hops_str:<6} {latency_str:<10} {xrp_str:<14} {stellar_str:<14} {rep:<5} {internet_icon:<9} {tor_str:<6} {last_seen_str:<15}")
        print("=" * 120)
        
        assets = peer.get('assets', [])
        if isinstance(assets, list) and assets:
            print(f"   Assets: {', '.join(assets)}")
        
        fee = peer.get('fee', 'N/A')
        fee_asset = peer.get('fee_asset', '')
        if fee != 'N/A':
            print(f"   Fee: {fee} {fee_asset}")
        
        if peer.get('reliability') is not None:
            print(f"   Reliability: {peer.get('reliability', 0):.2f}")
        if peer.get('networks'):
            print(f"   Networks: {', '.join(peer.get('networks', []))}")
        
        # 🔥 MOSTRA STATO TOR IN DETTAGLIO
        if tor_enabled:
            print(f"   TOR: {'✅ Raggiungibile' if tor_reachable else '⚠️ Non raggiungibile'}")
        else:
            print(f"   TOR: ❌ Non attivo")

    def request_gateway_info(self, gateway_id: str) -> Dict[str, Any]:
        """Richiede info a un gateway specifico e RESTITUISCE IL PEER AGGIORNATO"""
        if not self.metrics:
            return {"success": False, "message": "Metrics not available"}
        
        # 🔥 CHIEDI INFO E ASPETTA RISPOSTA
        success = self.metrics.request_gateway_info(gateway_id)
        
        if success:
            # 🔥 RECUPERA IL PEER AGGIORNATO
            peers = self.metrics.get_all_peers()
            for p in peers:
                if p.get('gateway_id') == gateway_id:
                    return {"success": True, "peer": p, "message": "Request sent and response received"}
            return {"success": True, "message": "Request sent, but peer not found in cache"}
        else:
            return {"success": False, "message": "Request failed"}
    
    def test_all_gateways(self) -> Dict[str, Any]:
        """Testa tutti i gateway attivi - USA GatewayMetrics con timeout più lungo per radio"""
        if not self.metrics:
            return {"success": False, "results": [], "count": 0, "message": "Metrics not available"}
        
        result = self.discover_gateways(active_only=True)
        if not result.get("success"):
            return {"success": False, "results": [], "count": 0, "message": result.get("message", "Errore")}
        
        gateways = result.get("gateways", [])
        if not gateways:
            return {"success": True, "results": [], "count": 0, "message": "Nessun gateway attivo trovato"}
        
        tested = 0
        successful = 0
        results = []
        
        # 🔥 TIMEOUT PIÙ LUNGO PER RADIO (60 secondi)
        timeout_seconds = 60
        
        for gw in gateways:
            gw_id = gw.get('gateway_id', '')
            name = gw.get('name', 'UNKNOWN')
            hops = gw.get('hops', '?')
            last_seen = gw.get('last_seen', int(time.time()))
            
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] 📡 Testando: {name} ({gw_id})")
            
            try:
                success = self.metrics.request_gateway_info(gw_id, timeout_seconds=timeout_seconds)
                tested += 1
                
                if success:
                    successful += 1
                    status = "✅ ONLINE"
                    print(f"   ✅ Risposta ricevuta!")
                    
                    peers = self.metrics.get_all_peers()
                    has_internet = False
                    tor_enabled = False
                    tor_reachable = False
                    for p in peers:
                        if p.get('gateway_id') == gw_id:
                            has_internet = p.get('has_internet', False)
                            tor_enabled = p.get('tor_enabled', False)
                            tor_reachable = p.get('tor_reachable', False)
                            break
                    
                    if tor_enabled and tor_reachable:
                        tor_status = "🧅✅"
                    elif tor_enabled:
                        tor_status = "🧅❌"
                    else:
                        tor_status = "—"
                else:
                    status = "❌ OFFLINE"
                    has_internet = False
                    tor_status = "—"
                    print(f"   ❌ Nessuna risposta")
                    
                    try:
                        import sqlite3
                        conn = sqlite3.connect("gateway_peers.db")
                        c = conn.cursor()
                        c.execute('''
                            INSERT OR REPLACE INTO gateway_peers 
                            (gateway_id, name, hops, is_online, last_seen, reputation, reliability,
                             xrp_reachable, stellar_reachable, has_internet, assets, networks,
                             latency_ms, fee, fee_asset, tor_enabled, tor_reachable)
                            VALUES (?, ?, ?, 0, ?, 50, 0, 0, 0, 0, '[]', '[]', NULL, 'N/A', '', 0, 0)
                        ''', (gw_id, name, hops, last_seen))
                        conn.commit()
                        conn.close()
                    except:
                        pass
                        
            except Exception as e:
                status = f"❌ ERRORE"
                has_internet = False
                tor_status = "—"
                print(f"   ❌ Errore: {e}")
                
                try:
                    import sqlite3
                    conn = sqlite3.connect("gateway_peers.db")
                    c = conn.cursor()
                    c.execute('''
                        INSERT OR REPLACE INTO gateway_peers 
                        (gateway_id, name, hops, is_online, last_seen, reputation, reliability,
                         xrp_reachable, stellar_reachable, has_internet, assets, networks,
                         latency_ms, fee, fee_asset, tor_enabled, tor_reachable)
                        VALUES (?, ?, ?, 0, ?, 50, 0, 0, 0, 0, '[]', '[]', NULL, 'N/A', '', 0, 0)
                    ''', (gw_id, name, hops, last_seen))
                    conn.commit()
                    conn.close()
                except:
                    pass
            
            results.append({
                "name": name,
                "gateway_id": gw_id,
                "hops": hops,
                "status": status,
                "has_internet": has_internet,
                "tor_status": tor_status
            })
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "tested": tested,
            "successful": successful,
            "message": f"Test completato: {successful}/{tested} gateway hanno risposto"
        }
    
    def remove_gateway(self, gateway_id: str) -> Dict[str, Any]:
        """
        Rimuove un gateway da announce_cache.db e gateway_peers.db
        """
        try:
            import sqlite3
            removed_from_announce = False
            removed_from_peers = False
            
            # 1. RIMUOVI DA announce_cache.db
            try:
                conn = sqlite3.connect("announce_cache.db")
                c = conn.cursor()
                
                # Prova a rimuovere dalla tabella gateway_announces
                c.execute("DELETE FROM gateway_announces WHERE gateway_id = ?", (gateway_id,))
                if c.rowcount > 0:
                    removed_from_announce = True
                
                # Prova anche da wallet_announces (se presente)
                try:
                    c.execute("DELETE FROM wallet_announces WHERE wallet_id = ?", (gateway_id,))
                except:
                    pass
                
                conn.commit()
                conn.close()
            except Exception as e:
                print_yellow(f"⚠️ Errore rimozione da announce_cache: {e}")
            
            # 2. RIMUOVI DA gateway_peers.db
            try:
                conn = sqlite3.connect("gateway_peers.db")
                c = conn.cursor()
                c.execute("DELETE FROM gateway_peers WHERE gateway_id = ?", (gateway_id,))
                if c.rowcount > 0:
                    removed_from_peers = True
                conn.commit()
                conn.close()
            except Exception as e:
                print_yellow(f"⚠️ Errore rimozione da gateway_peers: {e}")
            
            if removed_from_announce or removed_from_peers:
                return {
                    "success": True,
                    "removed_from_announce": removed_from_announce,
                    "removed_from_peers": removed_from_peers,
                    "message": f"Gateway {gateway_id[:16]}... rimosso"
                }
            else:
                return {"success": False, "message": "Gateway non trovato"}
                
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ============================================================
    # PASSWORD
    # ============================================================
    
    def change_password(self, old_password: str, new_password: str) -> Dict[str, Any]:
        if old_password != self._wallet_password:
            return {"success": False, "message": "Old password is incorrect"}
        if not new_password:
            return {"success": False, "message": "New password cannot be empty"}
        
        self._wallet_password = new_password
        if self.wallet and self.wallet._xrp_manager:
            self.wallet._xrp_manager._wallet_password = new_password
        
        # Ricifra tutti i wallet
        wallets = self._get_wallet_list()
        for w in wallets:
            wallet_file = self.wallets_dir / f"{w['name']}.json"
            if wallet_file.exists():
                with open(wallet_file, 'r') as f:
                    content = f.read().strip()
                data = self._decrypt_data(content)
                if data:
                    encrypted = self._encrypt_data(data)
                    with open(wallet_file, 'w') as f:
                        f.write(encrypted)
        self._invalidate_cache()
        return {"success": True, "message": "Password changed successfully"}
    
    def verify_password(self, password: str) -> Dict[str, Any]:
        if self.wallet and self.wallet._xrp_manager:
            self.wallet._xrp_manager._wallet_password = password
            if self.wallet._xrp_manager.load():
                return {"success": True, "message": "Password is correct"}
        return {"success": False, "message": "Password is incorrect"}
    
    # ============================================================
    # UTILITY - PUBBLICHE
    # ============================================================
    
    def get_status(self) -> Dict[str, Any]:
        wallets = self._get_wallet_list()
        active = self._get_active_wallet_name()
        reticulum_status = {}
        if self.reticulum:
            reticulum_status = self.reticulum.get_status()
        return {
            "initialized": self.wallet is not None,
            "active_wallet": active,
            "has_wallets": len(wallets) > 0,
            "wallet_count": len(wallets),
            "reticulum_active": self.reticulum is not None,
            "gateway_active": reticulum_status.get("is_gateway", False),
            "metrics_available": self.metrics is not None,
            "version": VERSION
        }
    
    def save(self) -> Dict[str, Any]:
        if self.wallet:
            self.wallet.save()
            return {"success": True, "message": "State saved"}
        return {"success": False, "message": "No wallet to save"}
    
    def get_error(self) -> Optional[str]:
        return None
    
    def clear_error(self):
        pass

# ============================================================
# FUNZIONE FACTORY
# ============================================================

def create_backend(password: str = None) -> WalletBackend:
    return WalletBackend(password=password)

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST WALLET BACKEND")
    print("=" * 60)
    
    backend = create_backend("testpassword")
    result = backend.init()
    print(f"Init: {result}")
    
    status = backend.get_status()
    print(f"Status: {status}")
    
    print("\n✅ Test completato!")