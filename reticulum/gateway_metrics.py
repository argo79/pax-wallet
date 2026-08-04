#!/usr/bin/env python3
"""
gateway_metrics.py - Gestione metriche tra gateway (STANDARD RETICULUM)
"""

import json5
import sqlite3
import json
import time
import threading
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List
import RNS
from dataclasses import dataclass


# ============================================================
# DEFINIZIONI MESSAGGI
# ============================================================

@dataclass
class GatewayInfoResponse:
    gateway_id: str
    name: str
    identity_hash: str
    networks: List[str]
    assets: List[str]
    fee: str
    fee_asset: str
    version: str
    has_internet: bool
    reputation: int
    uptime: int
    timestamp: int
    xrp_latency_ms: Optional[float] = None
    stellar_latency_ms: Optional[float] = None
    xrp_reachable: bool = False
    stellar_reachable: bool = False
    rssi: Optional[float] = None
    snr: Optional[float] = None
    quality: Optional[float] = None
    interface: Optional[str] = None
    latency_ms: Optional[float] = None
    hops: Optional[int] = None
    signature: str = ""
    tor_enabled: bool = False
    tor_reachable: bool = False


def sign_message(message: dict, identity) -> str:
    """Firma un messaggio con l'identity Reticulum"""
    msg_copy = {k: v for k, v in message.items() if k != "signature"}
    msg_json = json.dumps(msg_copy, sort_keys=True)
    signature = identity.sign(msg_json.encode())
    return signature.hex()


class GatewayMetrics:
    def __init__(self, identity, gateway_name: str = "Gateway", db_path: Path = Path("gateway_peers.db")):
        self.identity = identity
        self.db_path = db_path
        self.gateway_name = gateway_name
        self.lock = threading.Lock()
        self._my_gateway_id = None
        self._running = False
        self._query_thread = None
        self._ledger_cache = {
            "data": None,
            "last_check": 0
        }
        self._use_internet = True
        self._use_tor = False
        self._tor_reachable = False
        self._ledger_timeout = 5
        self._ledger_check_interval = 3600
        self._init_db()
    
    def set_use_internet(self, use_internet: bool):
        self._use_internet = use_internet
        self._ledger_cache["last_check"] = 0
        self._ledger_cache["data"] = None
        print(f"📡 Internet impostato a: {'ON' if use_internet else 'OFF'}")
    
    def set_use_tor(self, use_tor: bool):
        self._use_tor = use_tor
        if use_tor:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect(('127.0.0.1', 9050))
                sock.close()
                self._tor_reachable = True
                print("🧅 TOR raggiungibile")
            except:
                self._tor_reachable = False
                print("🧅 TOR non raggiungibile")
        else:
            self._tor_reachable = False
            print("🧅 TOR disattivato")
    
    def set_ledger_timeout(self, timeout: int):
        self._ledger_timeout = timeout
    
    def set_ledger_check_interval(self, interval: int):
        self._ledger_check_interval = interval
    
    def _init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS gateway_peers (
                    gateway_id TEXT PRIMARY KEY,
                    name TEXT,
                    identity_hash TEXT,
                    networks TEXT,
                    assets TEXT,
                    fee TEXT,
                    fee_asset TEXT,
                    version TEXT,
                    has_internet BOOLEAN,
                    reputation INTEGER DEFAULT 50,
                    hops INTEGER,
                    latency_ms INTEGER,
                    reliability REAL DEFAULT 0.5,
                    last_seen INTEGER,
                    last_updated INTEGER,
                    is_online BOOLEAN DEFAULT 1,
                    query_attempts INTEGER DEFAULT 0,
                    query_success INTEGER DEFAULT 0,
                    xrp_latency_ms INTEGER,
                    stellar_latency_ms INTEGER,
                    xrp_reachable BOOLEAN DEFAULT 0,
                    stellar_reachable BOOLEAN DEFAULT 0,
                    rssi REAL,
                    snr REAL,
                    quality REAL,
                    interface TEXT,
                    tor_enabled BOOLEAN DEFAULT 0,
                    tor_reachable BOOLEAN DEFAULT 0
                )
            ''')
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_hops ON gateway_peers(hops)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON gateway_peers(last_seen)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_reputation ON gateway_peers(reputation)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_rssi ON gateway_peers(rssi)')
            
            conn.commit()
            conn.close()
            print(f"✅ GatewayMetrics inizializzato: {self.db_path}")
    
    def set_my_gateway_id(self, gateway_id: str):
        self._my_gateway_id = gateway_id
    
    # ============================================================
    # CHECK LEDGER
    # ============================================================
    
    def check_ledger_full(self) -> Dict[str, Any]:
        if not self._use_internet:
            return {
                "has_internet": False,
                "xrp": {"reachable": False, "latency_ms": None},
                "stellar": {"reachable": False, "latency_ms": None},
                "timestamp": int(time.time())
            }
        
        timeout = self._ledger_timeout
        result = {
            "has_internet": True,
            "xrp": {"reachable": False, "latency_ms": None},
            "stellar": {"reachable": False, "latency_ms": None},
            "timestamp": int(time.time())
        }
        
        # Check XRP
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
        
        # Check Stellar
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
        interval = self._ledger_check_interval
        
        if (now - self._ledger_cache["last_check"]) > interval:
            self._ledger_cache["data"] = self.check_ledger_full()
            self._ledger_cache["last_check"] = now
        
        return self._ledger_cache["data"]
    
    # ============================================================
    # AGGIORNAMENTO DA ANNUNCI
    # ============================================================
    
    def update_from_announce(self, gateway_id: str, name: str, identity_hash: str = None,
                            hops: int = None, interface: str = None,
                            rssi: float = None, snr: float = None, quality: float = None):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            now = int(time.time())
            
            c.execute('SELECT gateway_id FROM gateway_peers WHERE gateway_id = ?', (gateway_id,))
            exists = c.fetchone()
            
            if exists:
                c.execute('''
                    UPDATE gateway_peers 
                    SET name = COALESCE(?, name),
                        identity_hash = COALESCE(?, identity_hash),
                        hops = COALESCE(?, hops),
                        interface = COALESCE(?, interface),
                        rssi = COALESCE(?, rssi),
                        snr = COALESCE(?, snr),
                        quality = COALESCE(?, quality),
                        last_seen = ?,
                        is_online = 1
                    WHERE gateway_id = ?
                ''', (name, identity_hash, hops, interface, rssi, snr, quality, now, gateway_id))
            else:
                c.execute('''
                    INSERT INTO gateway_peers 
                    (gateway_id, name, identity_hash, hops, interface, rssi, snr, quality, last_seen, is_online)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (gateway_id, name, identity_hash, hops, interface, rssi, snr, quality, now))
            
            conn.commit()
            conn.close()
    
    # ============================================================
    # COSTRUZIONE RISPOSTA - CON TOR
    # ============================================================
    
    def build_info_response(self, client_latency_ms: float = None, client_hops: int = None) -> GatewayInfoResponse:
        if not self._use_internet:
            return GatewayInfoResponse(
                gateway_id=self._my_gateway_id or self.identity.hash.hex(),
                name=self.gateway_name,
                identity_hash=self.identity.hash.hex(),
                networks=["xrpl", "stellar"],
                assets=["XRP", "RLUSD", "XLM"],
                fee="0.00001",
                fee_asset="RLUSD",
                version="1.0.0",
                has_internet=False,
                reputation=85,
                uptime=int(time.time()),
                timestamp=int(time.time()),
                xrp_latency_ms=None,
                stellar_latency_ms=None,
                xrp_reachable=False,
                stellar_reachable=False,
                latency_ms=client_latency_ms,
                hops=client_hops,
                tor_enabled=self._use_tor,
                tor_reachable=self._tor_reachable
            )
        
        ledger_status = self.get_ledger_status()
        
        return GatewayInfoResponse(
            gateway_id=self._my_gateway_id or self.identity.hash.hex(),
            name=self.gateway_name,
            identity_hash=self.identity.hash.hex(),
            networks=["xrpl", "stellar"],
            assets=["XRP", "RLUSD", "XLM"],
            fee="0.00001",
            fee_asset="RLUSD",
            version="1.0.0",
            has_internet=ledger_status.get("has_internet", False),
            reputation=85,
            uptime=int(time.time()),
            timestamp=int(time.time()),
            xrp_latency_ms=ledger_status.get("xrp", {}).get("latency_ms"),
            stellar_latency_ms=ledger_status.get("stellar", {}).get("latency_ms"),
            xrp_reachable=ledger_status.get("xrp", {}).get("reachable", False),
            stellar_reachable=ledger_status.get("stellar", {}).get("reachable", False),
            latency_ms=client_latency_ms,
            hops=client_hops,
            tor_enabled=self._use_tor,
            tor_reachable=self._tor_reachable
        )
    
    # ============================================================
    # SERVER - GESTISCE RICHIESTE IN ARRIVO
    # ============================================================
    
    def process_info_request(self, request_data: dict, link=None) -> Optional[str]:
        """Processa una richiesta info e invia risposta SEMPRE via Resource"""
        try:
            client_hops = request_data.get("hops", None)
            client_rtt = request_data.get("rtt_ms", None)
            
            response = self.build_info_response(client_rtt, client_hops)
            response_dict = {
                "gateway_id": response.gateway_id,
                "name": response.name,
                "identity_hash": response.identity_hash,
                "networks": response.networks,
                "assets": response.assets,
                "fee": response.fee,
                "fee_asset": response.fee_asset,
                "version": response.version,
                "has_internet": response.has_internet,
                "reputation": response.reputation,
                "uptime": response.uptime,
                "timestamp": response.timestamp,
                "xrp_latency_ms": response.xrp_latency_ms,
                "stellar_latency_ms": response.stellar_latency_ms,
                "xrp_reachable": response.xrp_reachable,
                "stellar_reachable": response.stellar_reachable,
                "latency_ms": response.latency_ms,
                "hops": response.hops,
                "tor_enabled": response.tor_enabled,
                "tor_reachable": response.tor_reachable,
                "signature": sign_message({
                    "gateway_id": response.gateway_id,
                    "name": response.name,
                    "identity_hash": response.identity_hash,
                    "networks": response.networks,
                    "assets": response.assets,
                    "fee": response.fee,
                    "fee_asset": response.fee_asset,
                    "version": response.version,
                    "has_internet": response.has_internet,
                    "reputation": response.reputation,
                    "uptime": response.uptime,
                    "timestamp": response.timestamp,
                    "xrp_latency_ms": response.xrp_latency_ms,
                    "stellar_latency_ms": response.stellar_latency_ms,
                    "xrp_reachable": response.xrp_reachable,
                    "stellar_reachable": response.stellar_reachable,
                    "latency_ms": response.latency_ms,
                    "hops": response.hops,
                    "tor_enabled": response.tor_enabled,
                    "tor_reachable": response.tor_reachable
                }, self.identity)
            }
            
            response_json = json.dumps(response_dict)
            response_bytes = response_json.encode()
            
            # 🔥 USA SEMPRE RESOURCE PER ESSERE SICURI (gestisce MTU automaticamente)
            if link is not None:
                print(f"📤 Invio risposta via Resource ({len(response_bytes)} bytes)")
                try:
                    from RNS import Resource
                    resource = Resource(link, response_bytes, is_response=True)
                    resource.set_timeout(30)
                    # Aspetta il completamento
                    start = time.time()
                    while not resource.is_complete() and (time.time() - start) < 30:
                        time.sleep(0.1)
                    if resource.is_complete():
                        print(f"✅ Resource inviato completato")
                    else:
                        print(f"⚠️ Resource non completato in tempo")
                    return None  # Già inviato
                except Exception as e:
                    print(f"⚠️ Errore invio Resource: {e}")
                    # Fallback: prova pacchetto
                    print(f"📤 Fallback a pacchetto ({len(response_bytes)} bytes)")
                    return response_json
            
            # Se link è None, ritorna JSON per essere inviato come pacchetto
            return response_json
            
        except Exception as e:
            print(f"⚠️ Errore processing info_request: {e}")
            return None
    
    # ============================================================
    # CLIENT - RICEZIONE RISPOSTA
    # ============================================================
    
    def process_info_response(self, response_data: str) -> bool:
        try:
            import re
            cleaned_data = re.sub(r'#.*$', '', response_data, flags=re.MULTILINE)
            cleaned_data = cleaned_data.strip()
            info = json.loads(cleaned_data)
            now = int(time.time())
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                
                c.execute('''
                    INSERT OR REPLACE INTO gateway_peers 
                    (gateway_id, name, identity_hash, networks, assets, fee, fee_asset,
                     version, has_internet, reputation, last_updated, query_success, 
                     query_attempts, is_online,
                     xrp_latency_ms, stellar_latency_ms, xrp_reachable, stellar_reachable,
                     latency_ms, hops, last_seen,
                     tor_enabled, tor_reachable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    info.get("gateway_id", ""),
                    info.get("name", "UNKNOWN"),
                    info.get("identity_hash", ""),
                    json.dumps(info.get("networks", [])),
                    json.dumps(info.get("assets", [])),
                    info.get("fee", "0.00001"),
                    info.get("fee_asset", "XRP"),
                    info.get("version", "1.0.0"),
                    1 if info.get("has_internet", False) else 0,
                    info.get("reputation", 50),
                    now,
                    info.get("xrp_latency_ms", None),
                    info.get("stellar_latency_ms", None),
                    1 if info.get("xrp_reachable", False) else 0,
                    1 if info.get("stellar_reachable", False) else 0,
                    info.get("latency_ms", None),
                    info.get("hops", None),
                    now,
                    1 if info.get("tor_enabled", False) else 0,
                    1 if info.get("tor_reachable", False) else 0
                ))
                
                c.execute('''
                    UPDATE gateway_peers 
                    SET reliability = CAST(query_success AS REAL) / query_attempts
                    WHERE query_attempts > 0 AND gateway_id = ?
                ''', (info.get("gateway_id", ""),))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"⚠️ Errore processing_info_response: {e}")
            return False
    
    # ============================================================
    # CLIENT - INVIO RICHIESTA
    # ============================================================
    
    def request_gateway_info(self, gateway_id: str, timeout_seconds: int = 30) -> bool:
        if gateway_id == self._my_gateway_id:
            print(f"⚠️ Tentativo di connettersi a se stesso, ignorato")
            return False
        
        try:
            from RNS import Link
            import re
            
            dest_hash = bytes.fromhex(gateway_id)
            
            hops = None
            if RNS.Transport.has_path(dest_hash):
                entry = RNS.Transport.path_table.get(dest_hash)
                if entry and len(entry) > 2:
                    hops = entry[2]
                    print(f"📊 Hops da path_table: {hops}")
            else:
                try:
                    RNS.Transport.request_path(dest_hash)
                    time.sleep(0.5)
                    if RNS.Transport.has_path(dest_hash):
                        entry = RNS.Transport.path_table.get(dest_hash)
                        if entry and len(entry) > 2:
                            hops = entry[2]
                            print(f"📊 Hops da path_table (refresh): {hops}")
                except Exception as e:
                    pass
            
            server_identity = RNS.Identity.recall(dest_hash)
            if not server_identity:
                print(f"⚠️ Identity non trovata")
                return False
            
            server_destination = RNS.Destination(
                server_identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "rns", "rec", "gateway"
            )
            
            link = Link(server_destination)
            
            # 🔥 IMPOSTA LA STRATEGIA PER ACCETTARE RESOURCE
            link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
            
            link_established = threading.Event()
            rtt_ms = None
            link_hops = None
            
            def on_link_established(link_obj):
                nonlocal rtt_ms, link_hops
                link_established.set()
                
                if hasattr(link_obj, 'rtt') and link_obj.rtt is not None:
                    rtt_ms = round(link_obj.rtt * 1000, 2)
                    print(f"✅ Link stabilito con {gateway_id[:32]} (RTT: {rtt_ms}ms)")
                else:
                    print(f"✅ Link stabilito con {gateway_id[:32]}")
                
                if hasattr(link_obj, 'hops') and link_obj.hops is not None:
                    link_hops = link_obj.hops
                    print(f"📊 Hops dal link: {link_hops}")
            
            link.set_link_established_callback(on_link_established)
            
            if not link_established.wait(timeout_seconds):
                print(f"⏰ Timeout link")
                link.teardown()
                return False
            
            # 🔥 VARIABILI PER LA RISPOSTA (RESOURCE O PACCHETTO)
            response_data = None
            resource_data = None
            resource_received = threading.Event()
            response_received = threading.Event()
            request_time = time.time()
            resource_error = None
            
            # 🔥 CALLBACK PER RESOURCE
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
            
            # 🔥 CALLBACK PER PACCHETTI (piccoli)
            def on_packet_received(message, packet):
                nonlocal response_data
                try:
                    response_data = message.decode()
                    response_received.set()
                except Exception as e:
                    print(f"⚠️ Errore decodifica pacchetto: {e}")
            
            link.set_packet_callback(on_packet_received)
            
            final_hops = link_hops if link_hops is not None else hops
            
            # 🔥 RICHIESTA MINIMALE (solo essenziale)
            request = {
                "type": "info_request",
                "from": self._my_gateway_id,
                "timestamp": int(time.time())
            }
            if final_hops is not None:
                request["hops"] = final_hops
            if rtt_ms is not None:
                request["rtt_ms"] = rtt_ms
            
            # 🔥 INVIA RICHIESTA COME PACCHETTO (piccolo, < 500 byte)
            request_json = json.dumps(request)
            print(f"📤 Richiesta info inviata a {gateway_id[:16]}... ({len(request_json)} bytes)")
            RNS.Packet(link, request_json.encode()).send()
            
            # 🔥 ASPETTA RISPOSTA (pacchetto o resource)
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                if resource_received.is_set():
                    break
                if response_received.is_set():
                    break
                time.sleep(0.1)
            
            # 🔥 SE ABBIAMO RICEVUTO UN RESOURCE
            if resource_received.is_set():
                if resource_data and not resource_error:
                    try:
                        response_data = resource_data.decode()
                        print(f"📥 Risposta da resource ({len(response_data)} bytes)")
                    except Exception as e:
                        print(f"❌ Errore decodifica resource: {e}")
                        link.teardown()
                        return False
                else:
                    print(f"❌ Errore resource: {resource_error}")
                    link.teardown()
                    return False
            
            # 🔥 SE ABBIAMO RICEVUTO UN PACCHETTO
            if response_received.is_set() and response_data:
                response_time = time.time()
                rtt_from_response = round((response_time - request_time) * 1000, 2)
                print(f"📊 Reticulum RTT: {rtt_from_response}ms (da request/response)")
                
                try:
                    cleaned_data = re.sub(r'#.*$', '', response_data, flags=re.MULTILINE)
                    response_json = json.loads(cleaned_data.strip())
                    if rtt_ms is not None:
                        response_json['latency_ms'] = rtt_ms
                    elif rtt_from_response is not None:
                        response_json['latency_ms'] = rtt_from_response
                    if final_hops is not None:
                        response_json['hops'] = final_hops
                    response_data = json.dumps(response_json)
                except Exception as e:
                    print(f"⚠️ Errore aggiunta hops/latency: {e}")
            
            # 🔥 PROCESS LA RISPOSTA
            if response_data:
                success = self.process_info_response(response_data)
                try:
                    link.teardown()
                except:
                    pass
                return success
            
            print(f"⏰ Timeout attesa risposta ({timeout_seconds}s)")
            try:
                link.teardown()
            except:
                pass
            return False
                        
        except Exception as e:
            print(f"⚠️ Errore: {e}")
            return False
    
    # ============================================================
    # RECUPERO PEER
    # ============================================================

    def get_all_peers(self) -> List[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT 
                    gateway_id, 
                    name, 
                    identity_hash,
                    hops, 
                    latency_ms,
                    reputation, 
                    reliability,
                    networks, 
                    assets, 
                    fee,
                    fee_asset,
                    has_internet, 
                    last_seen,
                    last_updated,
                    is_online,
                    query_attempts,
                    query_success,
                    xrp_latency_ms,
                    stellar_latency_ms,
                    xrp_reachable,
                    stellar_reachable,
                    rssi,
                    snr,
                    quality,
                    interface,
                    tor_enabled,
                    tor_reachable
                FROM gateway_peers
                ORDER BY is_online DESC, reputation DESC, hops ASC
            ''')
            rows = c.fetchall()
            conn.close()
            
            result = []
            for row in rows:
                peer = dict(row)
                
                # 🔥 CERCA IL NOME PIÙ RECENTE DA announce_cache.db
                try:
                    conn2 = sqlite3.connect("announce_cache.db")
                    c2 = conn2.cursor()
                    c2.execute('''
                        SELECT name FROM gateway_announces 
                        WHERE gateway_id = ? 
                        ORDER BY last_seen DESC LIMIT 1
                    ''', (peer.get('gateway_id'),))
                    row2 = c2.fetchone()
                    if row2 and row2[0]:
                        peer['name'] = row2[0]
                    conn2.close()
                except:
                    pass
                
                if peer.get('networks') and isinstance(peer['networks'], str):
                    try:
                        peer['networks'] = json.loads(peer['networks'])
                    except:
                        peer['networks'] = []
                if peer.get('assets') and isinstance(peer['assets'], str):
                    try:
                        peer['assets'] = json.loads(peer['assets'])
                    except:
                        peer['assets'] = []
                
                # 🔥 CONVERTI TOR IN BOOLEAN
                peer['tor_enabled'] = bool(peer.get('tor_enabled', False))
                peer['tor_reachable'] = bool(peer.get('tor_reachable', False))
                result.append(peer)
            return result

    def get_best_gateway(self, asset: str = None) -> Optional[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = '''
                SELECT 
                    gateway_id, 
                    name, 
                    identity_hash,
                    hops, 
                    latency_ms, 
                    reputation, 
                    reliability,
                    networks, 
                    assets, 
                    fee, 
                    fee_asset, 
                    has_internet,
                    last_seen,
                    last_updated,
                    is_online,
                    xrp_latency_ms,
                    stellar_latency_ms,
                    xrp_reachable,
                    stellar_reachable,
                    rssi,
                    snr,
                    quality,
                    tor_enabled,
                    tor_reachable
                FROM gateway_peers
                WHERE is_online = 1
                  AND has_internet = 1
            '''
            params = []
            
            if asset:
                query += ' AND assets LIKE ?'
                params.append(f'%"{asset}"%')
            
            query += '''
                ORDER BY 
                    COALESCE(hops, 999) ASC,
                    COALESCE(latency_ms, 99999) ASC,
                    COALESCE(reputation, 50) DESC,
                    COALESCE(reliability, 0.5) DESC
                LIMIT 1
            '''
            
            c.execute(query, params)
            row = c.fetchone()
            conn.close()
            
            if row:
                peer = dict(row)
                if peer.get('networks') and isinstance(peer['networks'], str):
                    try:
                        peer['networks'] = json.loads(peer['networks'])
                    except:
                        peer['networks'] = []
                if peer.get('assets') and isinstance(peer['assets'], str):
                    try:
                        peer['assets'] = json.loads(peer['assets'])
                    except:
                        peer['assets'] = []
                peer['tor_enabled'] = bool(peer.get('tor_enabled', False))
                peer['tor_reachable'] = bool(peer.get('tor_reachable', False))
                return peer
            return None
    

    def record_attempt(self, gateway_id: str, success: bool):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            now = int(time.time())
            
            c.execute('SELECT query_attempts, query_success FROM gateway_peers WHERE gateway_id = ?', (gateway_id,))
            row = c.fetchone()
            if row:
                attempts = row[0] if row[0] is not None else 0
                successes = row[1] if row[1] is not None else 0
            else:
                attempts = 0
                successes = 0
            
            attempts += 1
            if success:
                successes += 1
            
            c.execute('''
                UPDATE gateway_peers 
                SET last_attempt = ?,
                    query_attempts = ?,
                    query_success = ?,
                    is_online = ?
                WHERE gateway_id = ?
            ''', (now, attempts, successes, 1 if success else 0, gateway_id))
            
            reliability = successes / attempts if attempts > 0 else 0.5
            c.execute('''
                UPDATE gateway_peers 
                SET reliability = ?
                WHERE gateway_id = ?
            ''', (reliability, gateway_id))
            
            conn.commit()
            conn.close()

    def update_reticulum_latency(self, gateway_id: str, latency_ms: float):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                UPDATE gateway_peers 
                SET latency_ms = ?
                WHERE gateway_id = ?
            ''', (int(latency_ms), gateway_id))
            conn.commit()
            conn.close()

    def start_query_loop(self, interval: int = 3600, max_peers: int = 10, max_hops: int = 3):
        if self._running:
            return
        
        self._running = True
        self._query_thread = threading.Thread(
            target=self._query_loop,
            args=(interval, max_peers, max_hops),
            daemon=True
        )
        self._query_thread.start()
        print(f"📡 Query loop avviato (interval: {interval}s)")
    
    def stop_query_loop(self):
        self._running = False
        if self._query_thread:
            self._query_thread.join(timeout=2)
        print("📡 Query loop fermato")
    
    def _query_loop(self, interval: int, max_peers: int, max_hops: int):
        while self._running:
            try:
                time.sleep(interval)
                
                with self.lock:
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute('''
                        SELECT gateway_id 
                        FROM gateway_peers
                        WHERE is_online = 1
                          AND (last_updated IS NULL OR last_updated < strftime('%s', 'now') - 86400)
                        ORDER BY last_updated ASC
                        LIMIT ?
                    ''', (max_peers,))
                    rows = c.fetchall()
                    conn.close()
                
                for row in rows:
                    gateway_id = row["gateway_id"]
                    if gateway_id == self._my_gateway_id:
                        continue
                    
                    success = self.request_gateway_info(gateway_id)
                    
                    with self.lock:
                        conn = sqlite3.connect(self.db_path)
                        c = conn.cursor()
                        c.execute('''
                            UPDATE gateway_peers 
                            SET query_attempts = query_attempts + 1,
                                query_success = query_success + ?,
                                is_online = ?
                            WHERE gateway_id = ?
                        ''', (1 if success else 0, 1 if success else 0, gateway_id))
                        
                        c.execute('''
                            UPDATE gateway_peers 
                            SET reliability = CAST(query_success AS REAL) / query_attempts
                            WHERE query_attempts > 0 AND gateway_id = ?
                        ''', (gateway_id,))
                        conn.commit()
                        conn.close()
                    
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"⚠️ Errore nel query loop: {e}")
    
    def get_stats(self) -> Dict:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM gateway_peers')
            total = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM gateway_peers WHERE is_online = 1')
            online = c.fetchone()[0]
            c.execute('SELECT AVG(reputation) FROM gateway_peers WHERE is_online = 1')
            avg_reputation = c.fetchone()[0] or 0
            c.execute('SELECT AVG(latency_ms) FROM gateway_peers WHERE is_online = 1 AND latency_ms IS NOT NULL')
            avg_latency = c.fetchone()[0]
            c.execute('SELECT AVG(rssi) FROM gateway_peers WHERE is_online = 1 AND rssi IS NOT NULL')
            avg_rssi = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM gateway_peers WHERE is_online = 1 AND tor_enabled = 1 AND tor_reachable = 1')
            tor_peers = c.fetchone()[0]
            conn.close()
            
            return {
                "total_peers": total,
                "online_peers": online,
                "avg_reputation": round(avg_reputation, 2),
                "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
                "avg_rssi": round(avg_rssi, 2) if avg_rssi else None,
                "tor_peers": tor_peers
            }