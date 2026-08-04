#!/usr/bin/env python3
"""
reticulum_manager.py - Gestione Reticulum STANDARD UFFICIALE
"""

import RNS
from RNS import Reticulum, Transport, Identity, Destination, Packet, Link

# ============================================================
# PATCH PER PYINSTALLER - FORZA Interface
# ============================================================
try:
    from RNS.Interfaces import Interface
except ImportError:
    try:
        from RNS import Interface
    except ImportError:
        class Interface:
            pass
        if not hasattr(RNS, 'Interface'):
            setattr(RNS, 'Interface', Interface)
        if not hasattr(RNS, 'Interfaces'):
            class Interfaces:
                pass
            RNS.Interfaces = Interfaces
        setattr(RNS.Interfaces, 'Interface', Interface)

try:
    RNS.Reticulum
except:
    pass

import time
import threading
import json
import os
import socket
import sqlite3
import subprocess
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from io import BytesIO
from .announce_cache import AnnounceCache


class ReticulumConfig:
    def __init__(self, config_path: Path = Path("annuncio_config.json")):
        self.identity_file = Path("gateway_identity.rid")
        self.app_name = "rns"
        self.aspect1 = "rec"
        self.aspect2 = "gateway"
        self.full_aspect = f"{self.app_name}.{self.aspect1}.{self.aspect2}"
        
        self.announce_interval = 60
        self.gateway_name = "Gateway"
        self.wallet_name = "Wallet"
        self.use_internet = True
        self.use_tor = False
        self.tor_socks_port = 9050
        self.tor_timeout_seconds = 30
        self.ledger_check_interval = 3600
        self.ledger_timeout_seconds = 5
        self.query_interval = 3600
        self.max_peers_to_query = 10
        self.max_hops_for_query = 3
        self.query_timeout_seconds = 60
        self.wallet_announce_interval = 60
        self.peers_per_cycle = 2
        self.sync_timeout_seconds = 5
        self.background = False
        self.discover_since_seconds = 86400

        self._load_config(config_path)
    
    def _load_config(self, config_path: Path):
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                
                gw = data.get("gateway", {})
                self.discover_since_seconds = gw.get("discover_since_seconds", 86400)
                self.gateway_name = gw.get("name", self.gateway_name)
                self.announce_interval = gw.get("announce_interval", self.announce_interval)
                self.use_internet = gw.get("internet", "on").lower() == "on"
                self.use_tor = gw.get("use_tor", "off").lower() == "on"
                self.tor_socks_port = gw.get("tor_socks_port", 9050)
                self.tor_timeout_seconds = gw.get("tor_timeout_seconds", 30)
                self.ledger_check_interval = gw.get("ledger_check_interval", self.ledger_check_interval)
                self.ledger_timeout_seconds = gw.get("ledger_timeout_seconds", self.ledger_timeout_seconds)
                self.query_interval = gw.get("query_interval", self.query_interval)
                self.max_peers_to_query = gw.get("max_peers_to_query", self.max_peers_to_query)
                self.max_hops_for_query = gw.get("max_hops_for_query", self.max_hops_for_query)
                self.query_timeout_seconds = gw.get("query_timeout_seconds", self.query_timeout_seconds)
                
                w = data.get("wallet", {})
                self.wallet_name = w.get("name", self.wallet_name)
                self.wallet_announce_interval = w.get("announce_interval", self.wallet_announce_interval)
                
                sync = data.get("sync", {})
                self.peers_per_cycle = sync.get("peers_per_cycle", self.peers_per_cycle)
                self.sync_timeout_seconds = sync.get("timeout_seconds", self.sync_timeout_seconds)
                
                self.background = data.get("background", self.background)
                
                print(f"✅ Config caricata da {config_path}")
            except Exception as e:
                print(f"⚠️ Errore caricamento config: {e}")


class AnnounceHandler:
    def __init__(self, aspect_filter=None):
        self.count = 0
        self.cache = {}
        self.lock = threading.Lock()
        self.aspect_filter = aspect_filter
        self.sqlite_cache = AnnounceCache()
        self._latency_cache = {}

    def received_announce(self, destination_hash, announced_identity, app_data):
        with self.lock:
            self.count += 1
            peer_hash = destination_hash.hex()
            
            name = "UNKNOWN"
            if app_data:
                try:
                    name = app_data.decode("utf-8")
                except:
                    name = "UNKNOWN"
            
            hops = None
            interface = None
            rssi = None
            snr = None
            quality = None
            
            if Transport.has_path(destination_hash):
                entry = Transport.path_table.get(destination_hash)
                if entry:
                    hops = entry[2] if len(entry) > 2 else None
                    if len(entry) > 5 and entry[5]:
                        interface = str(entry[5])[:50]
                        try:
                            if hasattr(entry[5], 'rssi'):
                                rssi = entry[5].rssi
                            if hasattr(entry[5], 'snr'):
                                snr = entry[5].snr
                            if hasattr(entry[5], 'quality'):
                                quality = entry[5].quality
                        except:
                            pass
            
            self.cache[peer_hash] = {
                "gateway_id": peer_hash,
                "gateway_name": name,
                "identity": announced_identity,
                "last_seen": int(time.time()),
                "hops": hops,
                "rssi": rssi,
                "snr": snr,
                "quality": quality,
                "interface": interface
            }
            
            identity_hash = announced_identity.hash.hex() if announced_identity else None
            
            if self.aspect_filter == "rns.rec.gateway":
                self.sqlite_cache.add_gateway_announce(
                    gateway_id=peer_hash,
                    name=name,
                    identity_hash=identity_hash,
                    hops=hops,
                    interface=interface,
                    rssi=rssi,
                    snr=snr,
                    quality=quality
                )
                
                parts = []
                if hops is not None:
                    parts.append(f"Hops:{hops}")
                if rssi is not None:
                    parts.append(f"RSSI:{rssi}dBm")
                if snr is not None:
                    parts.append(f"SNR:{snr}dB")
                if quality is not None:
                    parts.append(f"Q:{quality}%")
                if interface:
                    parts.append(f"IFACE:{interface[:20]}")
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📢 GATEWAY: {name} ({peer_hash}) {' '.join(parts)}")
                
            elif self.aspect_filter == "rns.rec.wallet":
                self.sqlite_cache.add_wallet_announce(
                    wallet_id=peer_hash,
                    name=name,
                    identity_hash=identity_hash,
                    hops=hops,
                    interface=interface,
                    rssi=rssi,
                    snr=snr,
                    quality=quality
                )
                
                parts = []
                if hops is not None:
                    parts.append(f"Hops:{hops}")
                if interface:
                    parts.append(f"IFACE:{interface[:20]}")
                if rssi is not None:
                    parts.append(f"RSSI:{rssi}dBm")
                if snr is not None:
                    parts.append(f"SNR:{snr}dB")
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📢 WALLET: {name} ({peer_hash}) {' '.join(parts)}")
            else:
                print(f"📢 ANNUNCIO: {name} ({peer_hash})")
    
    def get_cache_snapshot(self):
        with self.lock:
            return dict(self.cache)
    
    def get_cache_size(self):
        with self.lock:
            return len(self.cache)


class GatewayServerHandler:
    def __init__(self, identity, metrics, gateway_dest, gateway_id=None):
        self.identity = identity
        self.metrics = metrics
        self.gateway_dest = gateway_dest
        self._my_gateway_id = gateway_id
        self.latest_link = None
        self._active_links = []
        self._lock = threading.Lock()
        self._running = False
        self._link_latency = {}
        self._link_hops = {}
        self._pending_resources = {}
    
    def start(self):
        self._running = True
        self.gateway_dest.set_link_established_callback(self._on_link_established)
        print("📡 Gateway Server avviato su rns.rec.gateway")
    
    def stop(self):
        self._running = False
        with self._lock:
            for link in self._active_links:
                try:
                    if link and link.established:
                        link.teardown()
                except Exception as e:
                    print(f"⚠️ Errore chiusura link: {e}")
            self._active_links.clear()
            self.latest_link = None
        print("📡 Gateway Server fermato")
    
    def _on_link_established(self, link):
        print(f"✅ Client connesso!")
        
        with self._lock:
            self.latest_link = link
            self._active_links.append(link)
            
            if hasattr(link, 'rtt') and link.rtt is not None:
                latency = link.rtt * 1000
                self._link_latency[id(link)] = round(latency, 2)
                print(f"📊 Latenza link (RTT): {latency:.2f}ms")
            else:
                self._link_latency[id(link)] = None
                print(f"📊 Latenza link: N/A (RTT non disponibile)")
            
            if hasattr(link, 'hops') and link.hops is not None:
                self._link_hops[id(link)] = link.hops
                print(f"📊 Hops: {link.hops}")
        
        link.set_packet_callback(self._handle_packet)
        link.set_resource_strategy(RNS.Link.ACCEPT_NONE)
        link.set_link_closed_callback(self._on_link_closed)
    
    def _on_link_closed(self, link):
        print("❌ Client disconnesso")
        with self._lock:
            if link in self._active_links:
                self._active_links.remove(link)
            if self.latest_link == link:
                self.latest_link = None
            if id(link) in self._link_latency:
                del self._link_latency[id(link)]
            if id(link) in self._link_hops:
                del self._link_hops[id(link)]
    
    def get_link_latency(self, link_id):
        with self._lock:
            return self._link_latency.get(link_id)
    
    def get_link_hops(self, link_id):
        with self._lock:
            return self._link_hops.get(link_id)
    
    def _handle_packet(self, message, packet):
        try:
            if not message:
                print("⚠️ Pacchetto vuoto ricevuto")
                return
            
            # 🔥 PRIMA PROVA A DECODIFICARE COME JSON
            data = None
            try:
                data = json.loads(message.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Potrebbe essere un Resource (dati binari)
                print("📥 Pacchetto non JSON (probabilmente Resource), ignoro")
                return
            
            if not isinstance(data, dict):
                print(f"⚠️ Pacchetto non è un dict: {type(data)}")
                return
            
            print(f"📥 Pacchetto ricevuto: {data.get('type', 'unknown')}")
            
            # 🔥 GESTISCI RICHIESTE INFO
            if data.get("type") == "info_request":
                if not self.metrics:
                    print("⚠️ Metrics non disponibile, ignoro richiesta info")
                    return
                
                try:
                    response = self.metrics.process_info_request(data, link=packet.link)
                    
                    if response:
                        response_bytes = response.encode()
                        
                        if len(response_bytes) > 450:
                            print(f"📤 Risposta grande ({len(response_bytes)} bytes), uso Resource...")
                            self._send_response_as_resource(packet.link, response_bytes)
                        else:
                            Packet(packet.link, response_bytes).send()
                            print(f"📤 Risposta info inviata ({len(response_bytes)} bytes)")
                        
                        try:
                            time.sleep(0.1)
                            if packet.link and packet.link.is_established():
                                packet.link.teardown()
                                print("🔗 Link chiuso dopo risposta")
                        except:
                            pass
                    else:
                        print("⚠️ Nessuna risposta generata")
                except Exception as e:
                    print(f"⚠️ Errore generazione risposta info: {e}")
                    import traceback
                    traceback.print_exc()
                return
            
            # 🔥 GESTISCI RICHIESTE LEDGER RELAY
            if data.get("type") == "ledger_relay":
                if not self.metrics:
                    print("⚠️ Metrics non disponibile, ignoro richiesta ledger_relay")
                    return
                
                operation = data.get("operation")
                payload = data.get("payload", {})
                
                print(f"📥 Richiesta ledger_relay: {operation}")
                
                if operation == "get_balance":
                    result = self._handle_get_balance(payload)
                elif operation == "get_history":
                    result = self._handle_get_history(payload)
                elif operation == "submit_transaction":
                    result = self._handle_submit_transaction(payload)
                elif operation == "get_account_info":
                    result = self._handle_get_account_info(payload)
                elif operation == "get_ledger_info":
                    result = self._handle_get_ledger_info(payload)
                else:
                    result = {"error": f"Operazione non supportata: {operation}"}
                
                # 🔥 COSTRUISCI RISPOSTA
                use_tor = self.metrics._use_tor if hasattr(self.metrics, '_use_tor') else False
                tor_reachable = self.metrics._tor_reachable if hasattr(self.metrics, '_tor_reachable') else False
                
                if result.get("error"):
                    response_data = {
                        "type": "ledger_relay_response",
                        "success": False,
                        "error": result["error"],
                        "timestamp": int(time.time()),
                        "gateway_id": self._my_gateway_id,
                        "tor_enabled": use_tor,
                        "tor_reachable": tor_reachable
                    }
                else:
                    response_data = {
                        "type": "ledger_relay_response",
                        "success": True,
                        "result": result,
                        "timestamp": int(time.time()),
                        "gateway_id": self._my_gateway_id,
                        "tor_enabled": use_tor,
                        "tor_reachable": tor_reachable
                    }
                
                response_bytes = json.dumps(response_data).encode()
                
                # 🔥 SE TROPPO GRANDE PER MTU 500, USA RESOURCE
                if len(response_bytes) > 450:
                    print(f"📤 Risposta ledger grande ({len(response_bytes)} bytes), uso Resource...")
                    self._send_response_as_resource(packet.link, response_bytes)
                else:
                    Packet(packet.link, response_bytes).send()
                    print(f"📤 Risposta ledger inviata ({len(response_bytes)} bytes)")
                
                try:
                    time.sleep(0.1)
                    if packet.link and packet.link.is_established():
                        packet.link.teardown()
                        print("🔗 Link chiuso dopo risposta ledger")
                except:
                    pass
                return
            
            print(f"📥 Tipo pacchetto sconosciuto: {data.get('type')}")
                
        except Exception as e:
            print(f"⚠️ Errore critico elaborazione pacchetto: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if packet and hasattr(packet, 'link') and packet.link:
                try:
                    if packet.link.is_established():
                        packet.link.teardown()
                        print("🔗 Link chiuso (cleanup finale)")
                except:
                    pass
    
    def _send_response_as_resource(self, link, data: bytes):
        """Invia dati grandi come Resource usando un file temporaneo"""
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            
            file_obj = open(tmp_path, 'rb')
            
            resource = RNS.Resource(
                file_obj,
                link,
                callback=lambda r: self._resource_sent_callback(r, tmp_path)
            )
            resource.data_size = len(data)
            
            print(f"📤 Resource in invio ({len(data)} bytes, file: {tmp_path})")
            
        except Exception as e:
            print(f"⚠️ Errore invio resource: {e}")
            import traceback
            traceback.print_exc()
    
    def _resource_sent_callback(self, resource, tmp_path=None):
        if tmp_path:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    print(f"🗑️ File temporaneo rimosso: {tmp_path}")
            except Exception as e:
                print(f"⚠️ Errore rimozione file: {e}")
        
        if resource.status == RNS.Resource.COMPLETE:
            print("✅ Resource inviato con successo")
        else:
            print(f"❌ Invio resource fallito: {resource.status}")
    
    def _handle_submit_transaction(self, payload: Dict) -> Dict:
        tx_blob = payload.get("tx_blob")
        network = payload.get("network", "mainnet")
        
        if not tx_blob:
            return {"error": "tx_blob mancante"}
        
        try:
            from xrpl.transaction import submit_and_wait
            from xrpl.clients import JsonRpcClient
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(network, urls["mainnet"]))
            
            response = submit_and_wait(tx_blob, client)
            
            return {
                "hash": response.result.get("hash", "unknown"),
                "result_code": response.result.get('meta', {}).get('TransactionResult', 'unknown'),
                "ledger": response.result.get("ledger_index")
            }
        except Exception as e:
            return {"error": str(e)}

    def _handle_get_ledger_info(self, payload: Dict) -> Dict:
        try:
            from xrpl.clients import JsonRpcClient
            from xrpl.models.requests import Ledger
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/"
            }
            network = payload.get("network", "mainnet")
            client = JsonRpcClient(urls.get(network, urls["mainnet"]))
            
            request = Ledger(ledger_index="validated")
            response = client.request(request)
            
            ledger_index = response.result.get("ledger_index", 0)
            fee = response.result.get("ledger", {}).get("base_fee", "10")
            
            return {
                "ledger_index": ledger_index,
                "base_fee": fee
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_get_balance(self, payload: Dict) -> Dict:
        address = payload.get("address")
        crypto = payload.get("crypto", "XRP")
        
        if not address:
            return {"error": "Indirizzo mancante"}
        
        try:
            if crypto == "XRP":
                from xrpl.account import get_balance
                from xrpl.clients import JsonRpcClient
                
                client = JsonRpcClient("https://s1.ripple.com:51234/")
                balance_drops = get_balance(address, client)
                balance = balance_drops / 1_000_000
                return {"balance": balance, "crypto": "XRP"}
            
            elif crypto == "XLM":
                try:
                    from stellar_sdk import Server
                    server = Server("https://horizon.stellar.org")
                    account = server.accounts().account_id(address).call()
                    for balance_data in account.get('balances', []):
                        if balance_data['asset_type'] == 'native':
                            return {"balance": float(balance_data['balance']), "crypto": "XLM"}
                    return {"balance": 0.0, "crypto": "XLM"}
                except ImportError:
                    return {"error": "Stellar SDK non disponibile"}
            
            return {"error": f"Crypto non supportata: {crypto}"}
            
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_get_account_info(self, payload: Dict) -> Dict:
        try:
            from xrpl.clients import JsonRpcClient
            from xrpl.models.requests import AccountInfo
            
            address = payload.get("address")
            network = payload.get("network", "mainnet")
            
            if not address:
                return {"error": "Indirizzo mancante"}
            
            urls = {
                "mainnet": "https://s1.ripple.com:51234/",
                "testnet": "https://s.altnet.rippletest.net:51234/"
            }
            client = JsonRpcClient(urls.get(network, urls["mainnet"]))
            
            request = AccountInfo(account=address, ledger_index="validated")
            response = client.request(request)
            
            account_data = response.result.get("account_data", {})
            sequence = account_data.get("Sequence", 0)
            balance = account_data.get("Balance", 0)
            ledger_index = response.result.get("ledger_index", 0)
            
            return {
                "sequence": sequence,
                "balance": balance,
                "address": address,
                "ledger_index": ledger_index
            }
        except Exception as e:
            return {"error": str(e)}

    def _handle_get_history(self, payload: Dict) -> Dict:
        address = payload.get("address")
        crypto = payload.get("crypto", "XRP")
        network = payload.get("network", "mainnet")
        limit = payload.get("limit", 10)
        
        if not address:
            return {"error": "Indirizzo mancante"}
        
        try:
            if crypto == "XRP":
                from xrpl.models.requests import AccountTx
                from xrpl.models.response import ResponseStatus
                from xrpl.clients import JsonRpcClient
                
                urls = {
                    "mainnet": "https://s1.ripple.com:51234/",
                    "testnet": "https://s.altnet.rippletest.net:51234/",
                    "devnet": "https://s.devnet.rippletest.net:51234/"
                }
                client = JsonRpcClient(urls.get(network, urls["mainnet"]))
                request = AccountTx(
                    account=address,
                    ledger_index_min=-1,
                    ledger_index_max=-1,
                    limit=limit,
                    forward=False
                )
                response = client.request(request)
                
                if response.status != ResponseStatus.SUCCESS:
                    return {"error": str(response.status)}
                
                transactions = response.result.get("transactions", [])
                return {
                    "transactions": transactions,
                    "count": len(transactions)
                }
            
            elif crypto == "XLM":
                try:
                    import requests
                    if network == "mainnet":
                        horizon = "https://horizon.stellar.org"
                    else:
                        horizon = "https://horizon-testnet.stellar.org"
                    
                    url = f"{horizon}/accounts/{address}/transactions?limit={limit}&order=desc"
                    response = requests.get(url, timeout=60)
                    
                    if response.status_code != 200:
                        return {"error": f"Horizon error: {response.status_code}"}
                    
                    data = response.json()
                    transactions = data.get('_embedded', {}).get('records', [])
                    return {
                        "transactions": transactions,
                        "count": len(transactions)
                    }
                except ImportError:
                    return {"error": "Requests non disponibile"}
            
            return {"error": f"Crypto non supportata: {crypto}"}
            
        except Exception as e:
            return {"error": str(e)}


class ReticulumManager:
    _instance = None
    _reticulum = None
    _handler_gateway = None
    _handler_wallet = None
    _server_handler = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        if config_path is None:
            config_path = Path("annuncio_config.json")
        self.config = ReticulumConfig(config_path)
        
        self.identity = None
        self.gateway_address = None
        self.wallet_address = None
        self.gateway_dest = None
        self.is_gateway = False
        self._announce_thread = None
        self._pid = None
        self._started_at = None
        self.metrics = None
        self._ledger_cache = {
            "data": None,
            "last_check": 0
        }
        
        self._load_identity()
        self._calculate_addresses()
        print(f"✅ ReticulumManager inizializzato")
        print(f"   Gateway Address: {self.gateway_address}")
        print(f"   Wallet Address:  {self.wallet_address}")
        print(f"   Internet: {'ON' if self.config.use_internet else 'OFF'}")

    def _load_identity(self):
        if self.config.identity_file.exists():
            self.identity = Identity.from_file(str(self.config.identity_file))
            print(f"✅ Identità caricata da {self.config.identity_file}")
        else:
            self.identity = Identity()
            self.identity.to_file(str(self.config.identity_file))
            print(f"✅ Nuova identità creata: {self.config.identity_file}")

    def _calculate_addresses(self):
        if not self.identity:
            return
        self.gateway_address = Destination.hash(
            self.identity,
            "rns", "rec", "gateway"
        ).hex()
        self.wallet_address = Destination.hash(
            self.identity,
            "rns", "rec", "wallet"
        ).hex()

    def check_ledger(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def check_ledger_full(self) -> Dict[str, Any]:
        if not self.config.use_internet:
            return {
                "has_internet": False,
                "xrp": {"reachable": False, "latency_ms": None},
                "stellar": {"reachable": False, "latency_ms": None},
                "timestamp": int(time.time())
            }
        
        timeout = self.config.ledger_timeout_seconds
        result = {
            "has_internet": True,
            "xrp": {"reachable": False, "latency_ms": None},
            "stellar": {"reachable": False, "latency_ms": None},
            "timestamp": int(time.time())
        }
        
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(("s1.ripple.com", 51234))
            latency = (time.time() - start) * 1000
            result["xrp"]["reachable"] = True
            result["xrp"]["latency_ms"] = round(latency, 2)
            sock.close()
        except:
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(("s.altnet.rippletest.net", 51234))
                latency = (time.time() - start) * 1000
                result["xrp"]["reachable"] = True
                result["xrp"]["latency_ms"] = round(latency, 2)
                sock.close()
            except:
                pass
        
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(("horizon.stellar.org", 443))
            latency = (time.time() - start) * 1000
            result["stellar"]["reachable"] = True
            result["stellar"]["latency_ms"] = round(latency, 2)
            sock.close()
        except:
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(("horizon-testnet.stellar.org", 443))
                latency = (time.time() - start) * 1000
                result["stellar"]["reachable"] = True
                result["stellar"]["latency_ms"] = round(latency, 2)
                sock.close()
            except:
                pass
        
        result["has_internet"] = result["xrp"]["reachable"] or result["stellar"]["reachable"]
        return result

    def get_ledger_status(self) -> Dict[str, Any]:
        now = int(time.time())
        interval = self.config.ledger_check_interval
        
        if (now - self._ledger_cache["last_check"]) > interval:
            self._ledger_cache["data"] = self.check_ledger_full()
            self._ledger_cache["last_check"] = now
        
        return self._ledger_cache["data"]

    def set_metrics(self, metrics):
        self.metrics = metrics
        print("📡 Metrics impostate")

    def init(self):
        if ReticulumManager._reticulum is not None:
            print("📡 Reticulum già in esecuzione")
            return
        
        ReticulumManager._reticulum = Reticulum()
        print("📡 Reticulum avviato")
        
        ReticulumManager._handler_gateway = AnnounceHandler("rns.rec.gateway")
        Transport.register_announce_handler(ReticulumManager._handler_gateway)
        print("📡 Handler gateway registrato per rns.rec.gateway")
        
        ReticulumManager._handler_wallet = AnnounceHandler("rns.rec.wallet")
        Transport.register_announce_handler(ReticulumManager._handler_wallet)
        print("📡 Handler wallet registrato per rns.rec.wallet")
        
        print("📡 Gateway in attesa di avvio. Usa 'Avvia gateway'.")

    def _announce_loop(self):
        while self.is_gateway:
            time.sleep(self.config.announce_interval)
            if self.is_gateway and self.gateway_dest:
                try:
                    self.gateway_dest.announce(app_data=self.config.gateway_name.encode("utf-8"))
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📢 Gateway annunciato: {self.config.gateway_name}")
                except Exception as e:
                    print(f"⚠️ Errore announce: {e}")

    def stop_gateway(self):
        self.is_gateway = False
        if self._announce_thread:
            self._announce_thread.join(timeout=2)
        self._pid = None
        self._started_at = None
        
        if ReticulumManager._server_handler:
            try:
                ReticulumManager._server_handler.stop()
            except Exception as e:
                print(f"⚠️ Errore fermo server: {e}")
            ReticulumManager._server_handler = None
        
        print("✅ Gateway fermato")

    def start_gateway(self, blocking: bool = True):
        if self.is_gateway:
            print("⚠️ Gateway già avviato")
            return
        
        if ReticulumManager._reticulum is None:
            self.init()
        
        if ReticulumManager._server_handler:
            try:
                ReticulumManager._server_handler.stop()
            except Exception as e:
                print(f"⚠️ Errore fermo server precedente: {e}")
            ReticulumManager._server_handler = None
        
        self.gateway_dest = Destination(
            self.identity,
            Destination.IN,
            Destination.SINGLE,
            "rns", "rec", "gateway"
        )
        self.gateway_dest.set_packet_callback(self._handle_packet)
        
        if self.metrics:
            ReticulumManager._server_handler = GatewayServerHandler(
                self.identity, 
                self.metrics, 
                self.gateway_dest,
                gateway_id=self.gateway_address
            )
            ReticulumManager._server_handler.start()
            
            self.metrics.set_use_tor(self.config.use_tor)
        else:
            print("⚠️ Metrics non disponibile, server /info non avviato")
        
        announce_data = self.config.gateway_name.encode("utf-8")
        self.gateway_dest.announce(app_data=announce_data)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📢 Annuncio inviato: {self.config.gateway_name}")
        
        self.is_gateway = True
        self._pid = os.getpid()
        self._started_at = int(time.time())
        
        self._announce_thread = threading.Thread(target=self._announce_loop, daemon=True)
        self._announce_thread.start()
        
        print(f"✅ Gateway avviato")
        print(f"   Aspect: rns.rec.gateway")
        print(f"   Gateway ID: {self.gateway_address}")
        print(f"   Nome: {self.config.gateway_name}")
        print(f"   Internet: {'ON' if self.config.use_internet else 'OFF'}")
        print(f"   TOR: {'ON' if self.config.use_tor else 'OFF'}")
        
        if blocking:
            print("\n🔄 In esecuzione. Premi Ctrl+C per fermare.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Interrotto...")
                self.stop_gateway()

    def _handle_packet(self, message, packet):
        """Gestisce pacchetti che arrivano DIRETTAMENTE al gateway_dest (senza link)"""
        try:
            if not message:
                return
            
            # 🔥 VERIFICA SE È UN PACCHETTO VIA LINK
            if hasattr(packet, 'link') and packet.link is not None:
                # I pacchetti via link sono gestiti da GatewayServerHandler
                # Ma se arrivano qui, potrebbero essere Resource
                print("📥 Pacchetto via link (dovrebbe essere gestito da GatewayServerHandler)")
                # Non fare nulla, GatewayServerHandler se ne occupa
                return
            
            # 🔥 PACCHETTI SENZA LINK (annunci, broadcast)
            try:
                data = json.loads(message.decode())
                if isinstance(data, dict):
                    print(f"📥 Pacchetto senza link: {data.get('type', 'unknown')}")
            except:
                print("📥 Pacchetto senza link (non JSON)")
            
        except Exception as e:
            print(f"⚠️ Errore: {e}")
        finally:
            if packet and hasattr(packet, 'link') and packet.link:
                try:
                    if packet.link.is_established():
                        packet.link.teardown()
                except:
                    pass

    def discover_gateways(self) -> List[Dict]:
        print("🔍 Cerco gateway su Reticulum...")
        if ReticulumManager._handler_gateway is None:
            print("   ⚠️ Handler gateway non inizializzato")
            return []
        
        discover_since = getattr(self.config, 'discover_since_seconds', 86400)
        since = int(time.time()) - discover_since
        
        gateways = ReticulumManager._handler_gateway.sqlite_cache.get_gateway_announces(
            limit=100, 
            since=since
        )
        
        if gateways:
            my_id = self.gateway_address
            gateways = [g for g in gateways if g.get('gateway_id') != my_id]
            print(f"   Trovati {len(gateways)} gateway (escluso se stesso)")
            for gw in gateways:
                parts = []
                if gw.get('hops') is not None:
                    parts.append(f"Hops:{gw.get('hops')}")
                if gw.get('rssi') is not None:
                    parts.append(f"RSSI:{gw.get('rssi')}dBm")
                if gw.get('snr') is not None:
                    parts.append(f"SNR:{gw.get('snr')}dB")
                if gw.get('quality') is not None:
                    parts.append(f"Q:{gw.get('quality')}%")
                
                print(f"      - {gw.get('name', 'Sconosciuto')}) ({gw.get('gateway_id')}) {' '.join(parts)}")
        else:
            print(f"   ⚠️ Nessun gateway trovato nella cache (ultimi {discover_since//3600} ore)")
        
        return gateways

    def discover_wallets(self) -> List[Dict]:
        print("🔍 Cerco wallet su Reticulum...")
        if ReticulumManager._handler_wallet is None:
            print("   ⚠️ Handler wallet non inizializzato")
            return []
        
        since = int(time.time()) - 60
        wallets = ReticulumManager._handler_wallet.sqlite_cache.get_wallet_announces(limit=100, since=since)
        
        if wallets:
            print(f"   Trovati {len(wallets)} wallet")
            for w in wallets:
                parts = []
                if w.get('hops') is not None:
                    parts.append(f"Hops:{w.get('hops')}")
                if w.get('rssi') is not None:
                    parts.append(f"RSSI:{w.get('rssi')}dBm")
                if w.get('snr') is not None:
                    parts.append(f"SNR:{w.get('snr')}dB")
                
                print(f"      - {w.get('name', 'Sconosciuto')} ({w.get('wallet_id')}) {' '.join(parts)}")
        else:
            print("   ⚠️ Nessun wallet trovato nella cache (ultimi 60s)")
        
        return wallets

    def send_transaction_via_reticulum(self, gateway_id: str, tx_data: Dict) -> Dict:
        try:
            dest_hash = bytes.fromhex(gateway_id)
            packet = Packet(dest_hash, json.dumps(tx_data).encode())
            packet.send()
            return {"success": True, "status": "sent", "hash": gateway_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict:
        announces = 0
        gateway_count = 0
        wallet_count = 0
        
        if ReticulumManager._handler_gateway:
            with ReticulumManager._handler_gateway.lock:
                gateway_count = ReticulumManager._handler_gateway.sqlite_cache.count_gateway_announces()
                announces += ReticulumManager._handler_gateway.count
        
        if ReticulumManager._handler_wallet:
            with ReticulumManager._handler_wallet.lock:
                wallet_count = ReticulumManager._handler_wallet.sqlite_cache.count_wallet_announces()
                announces += ReticulumManager._handler_wallet.count
        
        ledger_status = self.get_ledger_status()
        
        return {
            "running": ReticulumManager._reticulum is not None,
            "is_gateway": self.is_gateway,
            "gateway_running": self.is_gateway,
            "gateway_address": self.gateway_address,
            "wallet_address": self.wallet_address,
            "gateway_name": self.config.gateway_name,
            "wallet_name": self.config.wallet_name,
            "aspect": self.config.full_aspect,
            "announces_received": announces,
            "gateway_count": gateway_count,
            "wallet_count": wallet_count,
            "pid": self._pid,
            "started_at": self._started_at,
            "use_internet": self.config.use_internet,
            "use_tor": self.config.use_tor,
            "has_internet": ledger_status.get("has_internet", False),
            "xrp_reachable": ledger_status.get("xrp", {}).get("reachable", False),
            "xrp_latency_ms": ledger_status.get("xrp", {}).get("latency_ms"),
            "stellar_reachable": ledger_status.get("stellar", {}).get("reachable", False),
            "stellar_latency_ms": ledger_status.get("stellar", {}).get("latency_ms")
        }


if __name__ == "__main__":
    manager = ReticulumManager()
    manager.init()
    manager.start_gateway()
    
    print("\n🔄 In esecuzione. Premi Ctrl+C per fermare.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Fermando...")
        manager.stop_gateway()